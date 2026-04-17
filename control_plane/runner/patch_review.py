"""Patch-review orchestrator.

Sequential per-task Opus review of a whole patch, with TL;DRs carried
forward between steps, and a final synthesis step rendering the ship
verdict. Replaces the retired per-task OPUS_REVIEWER path — the
structural gate + Sonnet triage now handle per-task approval, and this
orchestrator is the sole Opus gate before a patch ships.

State machine is persisted in `patch_reviews` so a server crash
mid-review resumes from disk on restart (see `resume_in_progress()`,
wired into routes/runs.py next to the startup reaper).
"""
from __future__ import annotations

import glob
import json
import logging
import re
import secrets
from pathlib import Path

from ..config import SETTINGS
from ..db import get_conn
from .base import RunRequest
from .cli_adapter import ClaudeCliAdapter
from .dispatcher import DISPATCHER
from .prompts import (
    build_patch_review_step_prompt,
    build_patch_synthesis_prompt,
)


log = logging.getLogger(__name__)


def _new_run_id() -> str:
    return "RUN_" + secrets.token_hex(6).upper()


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Patch + task loaders
# ---------------------------------------------------------------------------


def _load_patch(patch_id: str) -> dict | None:
    row = get_conn().execute(
        "SELECT * FROM patches WHERE patch_id=?", (patch_id,),
    ).fetchone()
    return dict(row) if row else None


def _load_patch_review(patch_id: str) -> dict | None:
    row = get_conn().execute(
        "SELECT * FROM patch_reviews WHERE patch_id=?", (patch_id,),
    ).fetchone()
    return dict(row) if row else None


def _tasks_in_patch_ordered(patch_id: str) -> list[dict]:
    """Tasks for this patch in review order: patch_order asc, then updated_at."""
    rows = get_conn().execute(
        "SELECT * FROM tasks WHERE patch_id=? "
        "ORDER BY patch_order ASC, updated_at ASC, task_id ASC",
        (patch_id,),
    ).fetchall()
    out: list[dict] = []
    for r in rows:
        d = dict(r)
        for key in ("allowed_files", "forbidden_files"):
            try:
                d[key] = json.loads(d.get(key) or "[]")
            except Exception:
                d[key] = []
        out.append(d)
    return out


def _load_handoff_text(task: dict) -> str:
    brief_rel = task.get("brief_path") or \
        f"05_INBOX_FROM_MANAGER/HANDOFF_{task['task_id']}.md"
    p = SETTINGS.bridge_root / Path(brief_rel)
    try:
        return p.read_text(encoding="utf-8")
    except Exception as e:
        return f"(HANDOFF unreadable: {e})"


def _load_result_text(task_id: str) -> str:
    """Read the most recent RESULT artifact for this task from the DB."""
    row = get_conn().execute(
        """SELECT a.content FROM task_artifacts ta
             JOIN artifacts a ON a.artifact_id = ta.artifact_id
            WHERE ta.task_id=? AND a.kind='RESULT'
         ORDER BY a.mtime DESC LIMIT 1""",
        (task_id,),
    ).fetchone()
    return (row["content"] if row else "") or ""


# ---------------------------------------------------------------------------
# TL;DR + DECISION extraction (file-first; stdout is a fallback)
# ---------------------------------------------------------------------------


_TLDR_ANCHOR_RX = re.compile(r"(?m)^\s*TL;DR\s*:\s*$")
_BULLET_RX = re.compile(r"^\s*[-*]\s+(.+)$")
_DECISION_RX = re.compile(r"(?im)^\s*DECISION\s*:\s*([A-Z_]+)(?:\s*[—\-:]\s*(.*))?$")


def _glob_newest_review(patch_id: str, task_id: str) -> Path | None:
    """Find the REVIEW_<task>.md for this step, tolerant of filename variance.

    Opus occasionally writes with a trailing space or slightly different
    case; taking the newest match of REVIEW_<TID>*.md under the patch
    review dir is more robust than requiring the exact path.
    """
    base = SETTINGS.bridge_root / "07_REVIEWS" / f"PATCH_{patch_id}"
    # Case-insensitive glob via two patterns (Windows is case-insensitive
    # natively but glob is case-sensitive on some Python setups).
    patterns = [
        str(base / f"REVIEW_{task_id}*.md"),
        str(base / f"review_{task_id.lower()}*.md"),
    ]
    candidates: list[Path] = []
    for pat in patterns:
        for p in glob.iglob(pat):
            candidates.append(Path(p))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _extract_tldr_and_decision(review_path: Path) -> tuple[str | None, str | None]:
    """Return (tldr_block, decision). Either may be None if not present."""
    try:
        text = review_path.read_text(encoding="utf-8")
    except Exception as e:
        log.warning("read review %s failed: %r", review_path, e)
        return None, None

    # DECISION:
    decision: str | None = None
    m = _DECISION_RX.search(text)
    if m:
        decision = m.group(1).upper().strip()
        tail = (m.group(2) or "").strip()
        if tail:
            decision = f"{decision} — {tail}"

    # TL;DR: anchor → next lines that are `- ...`
    tldr: str | None = None
    anchor_m = _TLDR_ANCHOR_RX.search(text)
    if anchor_m:
        after = text[anchor_m.end():].lstrip("\n")
        bullets: list[str] = []
        for ln in after.splitlines():
            bm = _BULLET_RX.match(ln)
            if bm:
                bullets.append(f"- {bm.group(1).strip()}")
                if len(bullets) >= 5:
                    break
            elif bullets:
                # non-bullet line after bullets started → stop
                break
            # else: skip leading blanks
        if bullets:
            tldr = "\n".join(bullets)
    return tldr, decision


# ---------------------------------------------------------------------------
# Launch helpers
# ---------------------------------------------------------------------------


def _launch_step(
    *,
    patch: dict,
    task: dict,
    prior_summaries: list[str],
    step_index: int,
    total_steps: int,
) -> str | None:
    handoff_text = _load_handoff_text(task)
    result_text = _load_result_text(task["task_id"])
    prompt = build_patch_review_step_prompt(
        patch=patch, task=task,
        handoff_text=handoff_text,
        result_json_text=result_text,
        prior_summaries=prior_summaries,
        step_index=step_index,
        total_steps=total_steps,
    )
    run_id = _new_run_id()
    req = RunRequest(
        run_id=run_id,
        task_id=task["task_id"],
        role="OPUS_PATCH_REVIEWER",
        adapter="claude_cli",
        task=task,
        created_by="auto_patch_review",
        patch_review_meta={
            "patch_id": patch["patch_id"],
            "step": step_index,
            "total": total_steps,
        },
    )
    adapter = ClaudeCliAdapter()
    argv = adapter.build_argv(req, prompt)
    row = DISPATCHER.launch(
        req, argv, prompt,
        stdout_transform=adapter.transform_stdout_line,
    )
    if (row or {}).get("status") == "failed":
        log.warning("patch-review step launch failed for %s step %d: %s",
                    patch["patch_id"], step_index, (row or {}).get("result_summary"))
        return None
    # Record run_id in the patch_reviews row immediately.
    _append_run_id(patch["patch_id"], run_id)
    return run_id


def _launch_synthesis(patch: dict, tasks: list[dict]) -> str | None:
    pr = _load_patch_review(patch["patch_id"])
    if pr is None:
        return None
    try:
        summaries = json.loads(pr.get("summaries_json") or "[]")
    except Exception:
        summaries = []
    try:
        failed_steps = json.loads(pr.get("failed_steps_json") or "[]")
    except Exception:
        failed_steps = []

    prompt = build_patch_synthesis_prompt(
        patch=patch, summaries=summaries,
        failed_steps=failed_steps, tasks=tasks,
    )
    run_id = _new_run_id()
    req = RunRequest(
        run_id=run_id,
        task_id=None,
        role="OPUS_PATCH_REVIEWER",
        adapter="claude_cli",
        task=None,
        created_by="auto_patch_review",
        patch_review_meta={
            "patch_id": patch["patch_id"],
            "synthesis": True,
        },
    )
    adapter = ClaudeCliAdapter()
    argv = adapter.build_argv(req, prompt)
    row = DISPATCHER.launch(
        req, argv, prompt,
        stdout_transform=adapter.transform_stdout_line,
    )
    if (row or {}).get("status") == "failed":
        log.warning("patch-review synthesis launch failed for %s: %s",
                    patch["patch_id"], (row or {}).get("result_summary"))
        return None
    get_conn().execute(
        "UPDATE patch_reviews SET synthesis_run_id=? WHERE patch_id=?",
        (run_id, patch["patch_id"]),
    )
    return run_id


def _append_run_id(patch_id: str, run_id: str) -> None:
    pr = _load_patch_review(patch_id)
    if pr is None:
        return
    try:
        ids = json.loads(pr.get("run_ids_json") or "[]")
    except Exception:
        ids = []
    ids.append(run_id)
    get_conn().execute(
        "UPDATE patch_reviews SET run_ids_json=? WHERE patch_id=?",
        (json.dumps(ids), patch_id),
    )


def _append_summary(patch_id: str, summary: str) -> None:
    pr = _load_patch_review(patch_id)
    if pr is None:
        return
    try:
        sums = json.loads(pr.get("summaries_json") or "[]")
    except Exception:
        sums = []
    sums.append(summary)
    get_conn().execute(
        "UPDATE patch_reviews SET summaries_json=? WHERE patch_id=?",
        (json.dumps(sums), patch_id),
    )


def _record_failed_step(patch_id: str, index: int, task_id: str, reason: str) -> None:
    pr = _load_patch_review(patch_id)
    if pr is None:
        return
    try:
        fails = json.loads(pr.get("failed_steps_json") or "[]")
    except Exception:
        fails = []
    fails.append({"index": index, "task_id": task_id, "reason": reason[:300]})
    get_conn().execute(
        "UPDATE patch_reviews SET failed_steps_json=? WHERE patch_id=?",
        (json.dumps(fails), patch_id),
    )


# ---------------------------------------------------------------------------
# Public API: start / advance / resume
# ---------------------------------------------------------------------------


def start(patch_id: str) -> dict:
    """Kick off a patch review. Returns a JSON-serializable status dict.

    Refuses to start if:
      - patch doesn't exist → {ok: False, error: 'patch_not_found'}
      - patch has no tasks → {ok: False, error: 'empty_patch'}
      - any task has blocked_on or block_reason → {ok: False,
        error: 'blocked_tasks', blockers: [...]}
      - a review is already in_progress → {ok: False, error: 'already_running',
        current: N, total: M}
    """
    patch = _load_patch(patch_id)
    if patch is None:
        return {"ok": False, "error": "patch_not_found"}

    existing = _load_patch_review(patch_id)
    if existing and existing["status"] == "in_progress":
        return {
            "ok": False, "error": "already_running",
            "current": existing["current_index"],
            "total": existing["total_steps"],
        }

    tasks = _tasks_in_patch_ordered(patch_id)
    if not tasks:
        return {"ok": False, "error": "empty_patch"}

    blocked = [
        {"task_id": t["task_id"], "blocked_on": t.get("blocked_on"),
         "block_reason": t.get("block_reason")}
        for t in tasks if t.get("blocked_on") or t.get("block_reason")
    ]
    if blocked:
        return {"ok": False, "error": "blocked_tasks", "blockers": blocked}

    now = _now_iso()
    conn = get_conn()
    if existing:
        # Re-run after a prior done/failed: reset the state.
        conn.execute(
            "UPDATE patch_reviews SET status='in_progress', current_index=0, "
            "total_steps=?, summaries_json='[]', run_ids_json='[]', "
            "failed_steps_json='[]', synthesis_run_id=NULL, final_decision=NULL, "
            "started_at=?, finished_at=NULL WHERE patch_id=?",
            (len(tasks), now, patch_id),
        )
    else:
        conn.execute(
            """INSERT INTO patch_reviews
               (patch_id, status, current_index, total_steps, summaries_json,
                run_ids_json, failed_steps_json, started_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (patch_id, "in_progress", 0, len(tasks),
             "[]", "[]", "[]", now),
        )

    run_id = _launch_step(
        patch=patch, task=tasks[0], prior_summaries=[],
        step_index=0, total_steps=len(tasks),
    )
    if not run_id:
        conn.execute(
            "UPDATE patch_reviews SET status='failed', finished_at=? WHERE patch_id=?",
            (now, patch_id),
        )
        return {"ok": False, "error": "launch_failed", "step": 0}
    return {"ok": True, "patch_id": patch_id, "run_id": run_id,
            "step": 0, "total": len(tasks)}


def on_step_finish(
    patch_id: str, step_index: int, total: int,
    finished_run_id: str, exit_code: int,
) -> None:
    """Capture hook entry-point after a patch-review step subprocess exits."""
    pr = _load_patch_review(patch_id)
    if pr is None:
        log.warning("on_step_finish: no patch_review row for %s", patch_id)
        return
    if pr["status"] != "in_progress":
        log.warning("on_step_finish: patch_review %s not in progress (%s)",
                    patch_id, pr["status"])
        return
    # Idempotency: skip stale callbacks from an earlier step that already advanced.
    if pr["current_index"] != step_index:
        log.info("on_step_finish: stale callback for %s (cb=%d, cur=%d) — ignored",
                 patch_id, step_index, pr["current_index"])
        return

    patch = _load_patch(patch_id)
    tasks = _tasks_in_patch_ordered(patch_id)
    if step_index >= len(tasks):
        log.warning("on_step_finish: step_index %d >= tasks %d for %s",
                    step_index, len(tasks), patch_id)
        return
    task = tasks[step_index]

    review_path = _glob_newest_review(patch_id, task["task_id"])
    tldr, decision = (None, None)
    if review_path:
        tldr, decision = _extract_tldr_and_decision(review_path)

    if exit_code == 0 and tldr:
        summary_block = tldr
        if decision:
            summary_block = f"DECISION: {decision}\n{tldr}"
        _append_summary(patch_id, summary_block)
    else:
        reason = (f"exit={exit_code}; "
                  f"review_file={'missing' if review_path is None else 'present'}; "
                  f"tldr={'missing' if not tldr else 'ok'}")
        _record_failed_step(patch_id, step_index, task["task_id"], reason)
        _append_summary(patch_id, f"[step {step_index} — {task['task_id']}] failed: {reason}")

    # Advance.
    next_index = step_index + 1
    conn = get_conn()
    conn.execute(
        "UPDATE patch_reviews SET current_index=? WHERE patch_id=?",
        (next_index, patch_id),
    )

    if next_index < total:
        try:
            sums = json.loads((_load_patch_review(patch_id) or {}).get("summaries_json") or "[]")
        except Exception:
            sums = []
        _launch_step(
            patch=patch, task=tasks[next_index],
            prior_summaries=sums,
            step_index=next_index, total_steps=total,
        )
    else:
        _launch_synthesis(patch, tasks)


def on_synthesis_finish(patch_id: str, finished_run_id: str, exit_code: int) -> None:
    """Capture hook entry-point after the synthesis run exits."""
    pr = _load_patch_review(patch_id)
    if pr is None:
        return
    final_path = SETTINGS.bridge_root / "07_REVIEWS" / f"PATCH_{patch_id}" / f"PATCH_REVIEW_{patch_id}.md"
    decision = None
    if final_path.exists():
        try:
            text = final_path.read_text(encoding="utf-8")
            m = _DECISION_RX.search(text)
            if m:
                decision = m.group(1).upper().strip()
                tail = (m.group(2) or "").strip()
                if tail:
                    decision = f"{decision} — {tail}"
        except Exception as e:
            log.warning("read synthesis %s failed: %r", final_path, e)
    status = "done" if (exit_code == 0 and decision) else "failed"
    get_conn().execute(
        "UPDATE patch_reviews SET status=?, final_decision=?, finished_at=? "
        "WHERE patch_id=?",
        (status, decision, _now_iso(), patch_id),
    )


def resume_in_progress() -> int:
    """Restart any patch reviews orphaned by a server crash.

    Called at startup after the dispatcher's zombie reaper has swept
    stuck 'running' run rows. Idempotent: if a step's REVIEW file is
    already on disk we treat the step as complete and advance.
    """
    rows = get_conn().execute(
        "SELECT patch_id, current_index, total_steps FROM patch_reviews "
        "WHERE status='in_progress'"
    ).fetchall()
    resumed = 0
    for r in rows:
        pid = r["patch_id"]
        # If a step run is already active, leave it alone.
        active = any(
            (rr.request.patch_review_meta or {}).get("patch_id") == pid
            for rr in list(getattr(DISPATCHER, "_runs", {}).values())
        )
        if active:
            continue
        patch = _load_patch(pid)
        tasks = _tasks_in_patch_ordered(pid)
        idx = r["current_index"]
        if idx >= len(tasks):
            _launch_synthesis(patch, tasks)
            resumed += 1
            continue
        task = tasks[idx]
        # If the current step's REVIEW already exists (crash between file
        # write and DB update), ingest it and advance without relaunching.
        existing = _glob_newest_review(pid, task["task_id"])
        if existing:
            tldr, decision = _extract_tldr_and_decision(existing)
            if tldr:
                block = f"DECISION: {decision}\n{tldr}" if decision else tldr
                _append_summary(pid, block)
                get_conn().execute(
                    "UPDATE patch_reviews SET current_index=? WHERE patch_id=?",
                    (idx + 1, pid),
                )
                if idx + 1 < len(tasks):
                    sums = json.loads((_load_patch_review(pid) or {}).get("summaries_json") or "[]")
                    _launch_step(patch=patch, task=tasks[idx + 1],
                                 prior_summaries=sums,
                                 step_index=idx + 1, total_steps=len(tasks))
                else:
                    _launch_synthesis(patch, tasks)
                resumed += 1
                continue
        # Otherwise re-launch the current step.
        try:
            sums = json.loads((_load_patch_review(pid) or {}).get("summaries_json") or "[]")
        except Exception:
            sums = []
        _launch_step(patch=patch, task=task, prior_summaries=sums,
                     step_index=idx, total_steps=r["total_steps"])
        resumed += 1
    return resumed
