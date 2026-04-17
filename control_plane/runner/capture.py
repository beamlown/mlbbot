"""Post-run capture: write result / review artifacts, link to task, transition.

Called by `dispatcher.RunDispatcher` exactly once per run, in the
run's own waiter thread. All DB writes use the shared autocommit
connection. This module is the bridge between raw subprocess output
and BOT_BRIDGE filesystem artifacts.

Worker role (HAIKU_WORKER):
  - parse final `RESULT_JSON:` line from stdout
  - write `06_OUTBOX_FROM_WORKER/RESULT_<TASK>.json`
  - link as artifact relation=result
  - leave task status alone — the operator or a reviewer advances it
    (the board will auto-show it as AWAITING_REVIEW because a result
    artifact is present).

Reviewer role (SONNET_MANAGER, OPUS_REVIEWER):
  - parse final `RESULT_JSON:` line for a `decision` field
    (APPROVED | CHANGES_REQUESTED | FAIL), fall back to scanning output
  - write `07_REVIEWS/REVIEW_<TASK>.md`
  - link as artifact relation=review
  - insert row into `reviews` table
  - if decision is APPROVED → task.status = DONE
  - if decision is CHANGES_REQUESTED / FAIL → task.status = CHANGES_REQUESTED

Auditor role (OPUS_AUDITOR, OPUS_ARCHITECT):
  - write `08_SHARED_CONTEXT/AUDIT_<TASK>.md`
  - link as artifact relation=audit

Architect/Manager runs without a task are allowed (ad-hoc strategy work)
and simply save the stdout transcript under `08_SHARED_CONTEXT/`.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from ..config import SETTINGS
from ..db import get_conn
from ..bridge.exporter import _now_iso  # re-use iso fmt
from ..bridge.importer import import_bot_bridge
from ..bridge.task_board_md import regenerate_board_md


_RESULT_RX = re.compile(r"^\s*RESULT_JSON:\s*(\{.*\})\s*$")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(SETTINGS.repo_root)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def _parse_result_json(lines: list[str]) -> dict | None:
    """Scan the buffered stdout tail for the last RESULT_JSON line."""
    for ln in reversed(lines):
        m = _RESULT_RX.match(ln)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                continue
    return None


def _write_artifact_row(*, kind: str, path: Path, title: str,
                        summary: str, content: str, task_ref: str | None) -> str:
    now = _now_iso()
    sha = _sha(content.encode("utf-8"))
    art_id = f"{kind}:{_rel(path)}"
    conn = get_conn()
    conn.execute(
        """INSERT INTO artifacts
             (artifact_id, kind, path, title, summary, task_ref,
              mtime, size_bytes, sha256, content, discovered_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(path) DO UPDATE SET
             kind=excluded.kind, title=excluded.title, summary=excluded.summary,
             task_ref=excluded.task_ref, mtime=excluded.mtime,
             size_bytes=excluded.size_bytes, sha256=excluded.sha256,
             content=excluded.content""",
        (art_id, kind, _rel(path), title, summary, task_ref,
         int(path.stat().st_mtime), path.stat().st_size, sha, content, now),
    )
    # Re-fetch the canonical id from the unique path.
    row = conn.execute(
        "SELECT artifact_id FROM artifacts WHERE path=?", (_rel(path),),
    ).fetchone()
    return row["artifact_id"] if row else art_id


def _link(task_id: str, artifact_id: str, relation: str) -> None:
    get_conn().execute(
        "INSERT OR IGNORE INTO task_artifacts(task_id, artifact_id, relation) "
        "VALUES (?,?,?)",
        (task_id, artifact_id, relation),
    )


def _outbox() -> Path:
    p = SETTINGS.bridge_root / "06_OUTBOX_FROM_WORKER"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _reviews_dir() -> Path:
    p = SETTINGS.bridge_root / "07_REVIEWS"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _shared_dir() -> Path:
    p = SETTINGS.bridge_root / "08_SHARED_CONTEXT"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _transcript_body(run: "_ActiveRun", result: dict | None) -> str:
    req = run.request
    header = [
        f"# Run transcript — {run.run_id}",
        "",
        f"- task: `{req.task_id or '(none)'}`",
        f"- role: `{req.role}`",
        f"- adapter: `{req.adapter}`",
        f"- started: {run.started_at}",
        f"- finished: {_now_iso()}",
        "",
    ]
    if result is not None:
        header += ["## RESULT_JSON", "", "```json", json.dumps(result, indent=2), "```", ""]
    try:
        stdout_text = run.stdout_path.read_text(encoding="utf-8")
    except Exception:
        stdout_text = "(stdout unreadable)"
    header += ["## stdout", "", "```", stdout_text.rstrip(), "```", ""]
    return "\n".join(header)


def _decision_from(result: dict | None, stdout_lines: list[str]) -> str | None:
    if result:
        d = (result.get("decision") or result.get("verdict") or "").upper().strip()
        if d:
            return _normalize_decision(d)
    # Scan stdout for a clear verdict line.
    for ln in reversed(stdout_lines):
        u = ln.strip().upper()
        if "APPROVED" in u:
            return "APPROVED"
        if "CHANGES_REQUESTED" in u or "CHANGES REQUESTED" in u:
            return "CHANGES_REQUESTED"
        if u.startswith("FAIL"):
            return "FAIL"
    return None


def _normalize_decision(d: str) -> str:
    d = d.upper().strip()
    if d.startswith("APPROV"):
        return "APPROVED"
    if d in ("CHANGES_REQUESTED", "CHANGES REQUESTED", "CR", "CHANGES"):
        return "CHANGES_REQUESTED"
    if d in ("FAIL", "FAILED", "REJECTED", "REJECT"):
        return "FAIL"
    if d in ("PROVISIONAL", "PROVISIONAL_APPROVED"):
        return "PROVISIONAL"
    return d


def finalize_run(run, exit_code: int) -> None:
    """Called by the dispatcher after the subprocess exits."""
    from ..roles import ROLE_INFO
    req = run.request
    task_id = req.task_id
    role = req.role
    result = _parse_result_json(run.last_lines)
    summary = (result or {}).get("summary") or f"exit={exit_code}"

    # Always stash the full transcript to 08_SHARED_CONTEXT (harmless for
    # tasks, and the only persisted output for task-less runs).
    if task_id:
        tbody = _transcript_body(run, result)
        tpath = _shared_dir() / f"TRANSCRIPT_{task_id}_{req.run_id[-8:]}.md"
        tpath.write_text(tbody, encoding="utf-8")

    info = ROLE_INFO.get(role)
    kind = info.kind if info else "worker"

    new_status: str | None = None
    artifact_ids: list[tuple[str, str]] = []

    if task_id and kind == "worker" and exit_code == 0:
        artifact_ids.append(_capture_worker(req, run, result))
    elif task_id and kind in ("reviewer", "manager"):
        aid, new_status = _capture_review(req, run, result, exit_code)
        if aid:
            artifact_ids.append(aid)
    elif task_id and kind in ("auditor", "architect"):
        artifact_ids.append(_capture_audit(req, run, result, kind))

    # Update run row with parsed summary.
    get_conn().execute(
        "UPDATE runs SET result_summary=? WHERE run_id=?",
        (summary[:500], req.run_id),
    )

    # Transition the task status if the reviewer decided. Export first so
    # the on-disk task_json reflects the new status BEFORE re-import runs;
    # otherwise the importer would read the stale file and undo the update.
    if task_id and new_status:
        get_conn().execute(
            "UPDATE tasks SET status=?, updated_at=? WHERE task_id=?",
            (new_status, _now_iso(), task_id),
        )
        try:
            from ..bridge.exporter import export_task
            export_task(task_id)
        except Exception:
            pass

    # Regenerate the markdown board BEFORE re-import. `_reconcile_board_rows`
    # treats CLAUDE_TASK_BOARD.md as authoritative for lane placement, so if
    # we skipped this step a freshly-approved task would bounce back to ACTIVE
    # on the next import.
    try:
        regenerate_board_md()
    except Exception:
        pass
    try:
        import_bot_bridge()
    except Exception:
        pass


def _capture_worker(req, run, result) -> tuple[str, str]:
    """Worker run: write RESULT_<TASK>.json under 06_OUTBOX_FROM_WORKER."""
    task_id = req.task_id
    payload = result or {"status": "ok", "summary": "(no RESULT_JSON emitted)"}
    payload.setdefault("task_id", task_id)
    payload.setdefault("role", req.role)
    payload.setdefault("run_id", req.run_id)
    payload.setdefault("captured_at", _now_iso())
    path = _outbox() / f"RESULT_{task_id}.json"
    body = json.dumps(payload, indent=2, ensure_ascii=False)
    path.write_text(body, encoding="utf-8")
    art_id = _write_artifact_row(
        kind="RESULT",
        path=path,
        title=f"RESULT_{task_id}",
        summary=str(payload.get("summary") or "")[:500],
        content=body,
        task_ref=task_id,
    )
    _link(task_id, art_id, "result")
    # Also stamp the task row.
    get_conn().execute(
        "UPDATE tasks SET result_path=?, updated_at=? WHERE task_id=?",
        (f"06_OUTBOX_FROM_WORKER/RESULT_{task_id}.json", _now_iso(), task_id),
    )
    return art_id, "result"


def _capture_review(req, run, result, exit_code) -> tuple[tuple[str, str] | None, str | None]:
    task_id = req.task_id
    # Gather a readable body.
    body_lines = [
        f"# REVIEW_{task_id}",
        "",
        f"- reviewer run: `{req.run_id}`",
        f"- reviewer role: `{req.role}`",
        f"- exit code: {exit_code}",
        "",
    ]
    decision = _decision_from(result, run.last_lines) or ("APPROVED" if exit_code == 0 else "CHANGES_REQUESTED")
    body_lines += [f"## Decision: **{decision}**", ""]
    if result:
        body_lines += ["## RESULT_JSON", "", "```json", json.dumps(result, indent=2), "```", ""]
    try:
        tail = "\n".join(run.last_lines[-80:])
    except Exception:
        tail = ""
    body_lines += ["## Transcript tail", "", "```", tail, "```", ""]
    body = "\n".join(body_lines)
    path = _reviews_dir() / f"REVIEW_{task_id}.md"
    path.write_text(body, encoding="utf-8")
    art_id = _write_artifact_row(
        kind="REVIEW",
        path=path,
        title=f"REVIEW_{task_id} ({decision})",
        summary=decision,
        content=body,
        task_ref=task_id,
    )
    _link(task_id, art_id, "review")

    # Insert into reviews table for history.
    get_conn().execute(
        """INSERT INTO reviews(review_id, task_id, run_id, decision, reviewer,
                               summary, artifact_id, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            f"REV_{req.run_id[-12:]}",
            task_id,
            req.run_id,
            decision,
            req.role,
            (result or {}).get("summary") if result else None,
            art_id,
            _now_iso(),
        ),
    )
    get_conn().execute(
        "UPDATE tasks SET review_path=?, updated_at=? WHERE task_id=?",
        (f"07_REVIEWS/REVIEW_{task_id}.md", _now_iso(), task_id),
    )

    # Task status transition.
    new_status = None
    if decision == "APPROVED":
        new_status = "DONE"
    elif decision in ("CHANGES_REQUESTED", "FAIL"):
        new_status = "CHANGES_REQUESTED"
    return (art_id, "review"), new_status


def _capture_audit(req, run, result, kind) -> tuple[str, str]:
    task_id = req.task_id
    path = _shared_dir() / f"AUDIT_{task_id}.md"
    lines = [
        f"# AUDIT_{task_id}",
        "",
        f"- run: `{req.run_id}`",
        f"- role: `{req.role}`",
        f"- kind: `{kind}`",
        "",
    ]
    if result:
        lines += ["## RESULT_JSON", "", "```json", json.dumps(result, indent=2), "```", ""]
    try:
        tail = "\n".join(run.last_lines[-120:])
    except Exception:
        tail = ""
    lines += ["## Transcript tail", "", "```", tail, "```", ""]
    body = "\n".join(lines)
    path.write_text(body, encoding="utf-8")
    art_id = _write_artifact_row(
        kind="AUDIT",
        path=path,
        title=f"AUDIT_{task_id}",
        summary=(result or {}).get("summary") if result else "",
        content=body,
        task_ref=task_id,
    )
    _link(task_id, art_id, "audit")
    return art_id, "audit"
