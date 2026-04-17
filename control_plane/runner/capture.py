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
_TRIAGE_RX = re.compile(r"^\s*TRIAGE:\s*(yes|no)\b\s*(.*)$", re.IGNORECASE)


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(SETTINGS.repo_root)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def _norm_path(p: str) -> str:
    """Collapse a path to forward-slash form for set comparison."""
    return (p or "").strip().replace("\\", "/").lstrip("./")


def _set_block(task_id: str, reason: str, *, blocked_on: str | None = None) -> None:
    """Populate the 'why stuck' signal on a task row.

    `block_reason` alone means the task is stuck for a content reason
    (structural failure, semantic triage fail, reviewer CR). `blocked_on`
    is additionally set when a specific task_id is the dependency blocker
    (used for auto-unblock on that dependency shipping).
    """
    now = _now_iso()
    if blocked_on:
        get_conn().execute(
            "UPDATE tasks SET blocked_on=?, block_reason=?, blocked_at=?, updated_at=? "
            "WHERE task_id=?",
            (blocked_on, reason[:500], now, now, task_id),
        )
    else:
        get_conn().execute(
            "UPDATE tasks SET block_reason=?, blocked_at=?, updated_at=? WHERE task_id=?",
            (reason[:500], now, now, task_id),
        )


def _clear_block(task_id: str) -> None:
    """Clear both block signals — call when the task is unblocked or succeeds."""
    now = _now_iso()
    get_conn().execute(
        "UPDATE tasks SET blocked_on=NULL, block_reason=NULL, blocked_at=NULL, "
        "updated_at=? WHERE task_id=?",
        (now, task_id),
    )


def _auto_unblock_dependents(finished_task_id: str) -> None:
    """When a task lands DONE, clear block fields on any task parked behind it.

    Only touches rows where `blocked_on` equals the finished task_id so
    free-text `block_reason`-only rows (structural/triage failures) stay
    stuck until their own root cause is addressed.
    """
    now = _now_iso()
    conn = get_conn()
    rows = conn.execute(
        "SELECT task_id FROM tasks WHERE blocked_on=?", (finished_task_id,),
    ).fetchall()
    for r in rows:
        tid = r["task_id"]
        conn.execute(
            "UPDATE tasks SET blocked_on=NULL, block_reason=NULL, blocked_at=NULL, "
            "updated_at=? WHERE task_id=?",
            (now, tid),
        )


def _structural_gate(task: dict | None, payload: dict) -> str | None:
    """Deterministic gate between worker RESULT and semantic triage.

    Returns None on pass, or a one-line failure reason on fail. Checks:
      - files_changed is a list
      - every files_changed entry is in allowed_files (if allowed is non-empty)
      - no files_changed entry is in forbidden_files
      - status == 'ok' (anything else is handled upstream)
    """
    task = task or {}
    allowed = task.get("allowed_files") or []
    forbidden = task.get("forbidden_files") or []
    if isinstance(allowed, str):
        try: allowed = json.loads(allowed)
        except Exception: allowed = []
    if isinstance(forbidden, str):
        try: forbidden = json.loads(forbidden)
        except Exception: forbidden = []

    files_changed = payload.get("files_changed")
    if not isinstance(files_changed, list):
        return "RESULT is missing files_changed (must be a list)"

    allowed_set = {_norm_path(p) for p in allowed if isinstance(p, str)}
    forbidden_set = {_norm_path(p) for p in forbidden if isinstance(p, str)}
    changed_set = {_norm_path(p) for p in files_changed if isinstance(p, str)}

    # No-op guard: when the task scoped a non-empty allowed_files, it is
    # by definition an EDIT task — the operator/manager said "these are
    # the files that may be touched." A worker that returns status='ok'
    # with files_changed=[] is declaring success without actually doing
    # anything. Without this check, such a run sails through the gate,
    # auto-DONEs, and lands in the pending patch with no material change
    # — the patch-review Opus then spends tokens on a no-op. Refuse here
    # so the operator sees the real signal immediately.
    #
    # Tasks with allowed_files=[] are intentionally unrestricted (audits,
    # read-only analyses that emit artifacts under 08_SHARED_CONTEXT).
    # Those are allowed to ship without a files_changed entry.
    if allowed_set and not changed_set:
        return (f"status='ok' but files_changed=[] despite {len(allowed_set)} "
                f"allowed_files scoped — no-op not accepted")

    if forbidden_set:
        violated = sorted(changed_set & forbidden_set)
        if violated:
            return f"files_changed touches forbidden_files: {violated[:3]}"

    if allowed_set:
        out_of_scope = sorted(changed_set - allowed_set)
        if out_of_scope:
            return f"files_changed contains paths not in allowed_files: {out_of_scope[:3]}"

    return None


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
        aid, relation, resolved = _capture_worker(req, run, result)
        artifact_ids.append((aid, relation))
        # File-first contract means the canonical summary lives in the
        # on-disk RESULT file, not stdout. Prefer it over the stdout parse.
        if resolved:
            disk_summary = resolved.get("summary")
            if disk_summary:
                summary = str(disk_summary)
            elif resolved.get("status"):
                summary = f"status={resolved.get('status')}"

            # Auto-transition the task based on what the worker actually
            # produced. `ok` → AWAITING_REVIEW so a reviewer picks it up.
            # `fail` / `blocked` → route back to READY_FOR_WORKER with an
            # updated HANDOFF that explains why the previous run failed, up
            # to a retry cap. After the cap, park in CHANGES_REQUESTED so
            # the operator decides the next move.
            payload_status = (resolved.get("status") or "").lower()
            if payload_status == "ok":
                # Structural gate: deterministic check on the RESULT shape.
                # Failures here block the task with a specific reason instead
                # of sending a malformed RESULT on to the semantic triage.
                gate_reason = _structural_gate(req.task, resolved)
                if gate_reason:
                    _set_block(task_id, f"structural: {gate_reason}")
                    new_status = "CHANGES_REQUESTED"
                else:
                    # Gate passed — auto-approve + auto-assign to the
                    # pending patch. The patch-review Opus is the ship
                    # gate, so per-task work that produces a well-formed
                    # RESULT and survives the structural check is treated
                    # as done; no need to stall in AWAITING_REVIEW waiting
                    # for a manual review step. Manual reviewers can still
                    # downgrade a task to CHANGES_REQUESTED if something
                    # needs a second look before the patch lands.
                    _clear_block(task_id)
                    new_status = "DONE"
                    try:
                        from ..patches import assign_task
                        assign_task(task_id)
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).warning(
                            "assign_task failed for %s: %r", task_id, e,
                        )
            elif payload_status in ("fail", "blocked"):
                # Zero-exit fails are not successes — keep the run row honest.
                if payload_status == "fail":
                    get_conn().execute(
                        "UPDATE runs SET status='failed' WHERE run_id=?",
                        (req.run_id,),
                    )
                # Count prior terminal-fail runs on this task (worker role).
                prior_fails = get_conn().execute(
                    """SELECT COUNT(*) c FROM runs
                        WHERE task_id=? AND role=? AND status IN ('failed','cancelled')""",
                    (task_id, req.role),
                ).fetchone()["c"]
                MAX_RETRIES = 3
                if prior_fails < MAX_RETRIES:
                    _append_retry_context_to_handoff(
                        task_id=task_id,
                        attempt=prior_fails,
                        run=run,
                        resolved=resolved,
                    )
                    # Board shows this via derive_state; keeping DB status
                    # QUEUED matches BOT_BRIDGE's existing vocabulary and
                    # lets `derive_state` route a retried task to
                    # READY_FOR_WORKER (no RESULT artifact kind flip needed
                    # because derive_state reads the RESULT payload status).
                    new_status = "QUEUED"
                else:
                    # Retry cap hit — surface a specific block reason so the
                    # operator sees why we stopped trying and doesn't launch
                    # this task again without addressing the root cause.
                    worker_reason = (resolved.get("notes")
                                     or resolved.get("summary")
                                     or f"worker returned status={payload_status}")
                    _set_block(
                        task_id,
                        f"retry cap hit ({MAX_RETRIES}): {worker_reason}",
                    )
                    new_status = "CHANGES_REQUESTED"
    elif task_id and kind in ("reviewer", "manager"):
        aid, new_status = _capture_review(req, run, result, exit_code)
        if aid:
            artifact_ids.append(aid)
    elif task_id and kind == "triage":
        # Sonnet triage: yes → DONE + auto-assign to pending patch; no →
        # CHANGES_REQUESTED + block_reason from the triage's reason text.
        new_status = _capture_triage(req, run, exit_code)
    elif kind == "patch_reviewer":
        # Route to the patch-review orchestrator based on the run's
        # patch_review_meta (stored on the runs row at launch time).
        _route_patch_review(req, run, exit_code)
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
        # Auto-unblock: any task parked behind this one is now unparked.
        if new_status == "DONE":
            _auto_unblock_dependents(task_id)
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


def _append_retry_context_to_handoff(*, task_id: str, attempt: int,
                                     run, resolved: dict) -> None:
    """Append a RETRY CONTEXT section to the task's HANDOFF explaining why
    the previous run failed, and clear the stale RESULT so the board
    derives the task back to READY_FOR_WORKER for another pass.

    `attempt` is the zero-indexed prior-fail count (so 0 on first retry).
    """
    # 1) Append retry context to the HANDOFF file.
    brief_rel = (run.request.task or {}).get("brief_path") \
        or f"05_INBOX_FROM_MANAGER/HANDOFF_{task_id}.md"
    brief_abs = SETTINGS.bridge_root / Path(brief_rel)
    try:
        prior = brief_abs.read_text(encoding="utf-8") if brief_abs.exists() else ""
    except Exception:
        prior = ""
    # Don't stack N copies of the retry section — replace if present.
    marker = "\n\n---\n## RETRY CONTEXT (auto-generated"
    if marker in prior:
        prior = prior.split(marker, 1)[0].rstrip() + "\n"
    summary = (resolved.get("summary") or "").strip()
    status = (resolved.get("status") or "?").strip()
    tail = ""
    try:
        tail = "\n".join(run.last_lines[-12:])
    except Exception:
        pass
    retry_block = (
        f"\n\n---\n## RETRY CONTEXT (auto-generated — attempt {attempt + 2})\n"
        f"\n"
        f"A previous run failed on this task. Before you start, read this:\n"
        f"\n"
        f"- prior status: `{status}`\n"
        f"- prior summary: {summary or '(none)'}\n"
        f"- prior run id: `{run.request.run_id}`\n"
        f"\n"
        f"### What went wrong\n"
        f"The previous worker did not produce a RESULT for **{task_id}**. "
        f"Common causes: (a) the worker drifted to a different task, "
        f"(b) the worker never wrote `RESULT_{task_id}.json`, "
        f"(c) the worker exited before completing the scope.\n"
        f"\n"
        f"### What to do differently this attempt\n"
        f"1. Work ONLY on `{task_id}`. Ignore every other task name you see.\n"
        f"2. Write your result to `BOT_BRIDGE/06_OUTBOX_FROM_WORKER/RESULT_{task_id}.json` "
        f"and NO other file.\n"
        f"3. If the scope is unclear, emit `status: blocked` with a specific question.\n"
        f"   Do NOT substitute a different task you think you know.\n"
        f"\n"
        f"### Prior stdout tail (for diagnosis)\n"
        f"```\n{tail.rstrip()[:1500]}\n```\n"
    )
    try:
        brief_abs.parent.mkdir(parents=True, exist_ok=True)
        brief_abs.write_text((prior.rstrip() + retry_block), encoding="utf-8")
    except Exception:
        pass

    # 2) Clear the stale RESULT artifact so derive_state routes this task
    # back to READY_FOR_WORKER rather than keeping it pinned in
    # AWAITING_REVIEW / CHANGES_REQUESTED by a fail-stub artifact.
    conn = get_conn()
    rows = conn.execute(
        """SELECT a.artifact_id, a.path FROM task_artifacts ta
             JOIN artifacts a ON a.artifact_id = ta.artifact_id
            WHERE ta.task_id=? AND a.kind='RESULT'""",
        (task_id,),
    ).fetchall()
    for r in rows:
        try:
            p = SETTINGS.repo_root / Path(r["path"])
            if p.exists():
                p.unlink()
        except Exception:
            pass
        conn.execute("DELETE FROM task_artifacts WHERE artifact_id=?", (r["artifact_id"],))
        conn.execute("DELETE FROM artifacts WHERE artifact_id=?", (r["artifact_id"],))


def _capture_worker(req, run, result) -> tuple[str, str, dict]:
    """Worker run: canonicalize RESULT_<TASK>.json under 06_OUTBOX_FROM_WORKER.

    Contract (file-first): the worker is expected to WRITE the result file
    directly. This function treats an on-disk file written during this run
    as canonical and never overwrites it. Stdout `RESULT_JSON:` is only
    used as a fallback when the worker skipped the file write.
    """
    task_id = req.task_id
    path = _outbox() / f"RESULT_{task_id}.json"

    # Parse run start into a unix timestamp so we can tell a fresh file
    # written by this run apart from a stale artifact from a prior run.
    try:
        start_ts = datetime.fromisoformat(run.started_at.replace("Z", "+00:00")).timestamp()
    except Exception:
        start_ts = 0.0

    worker_wrote_file = False
    payload: dict | None = None
    if path.exists():
        try:
            file_mtime = path.stat().st_mtime
        except Exception:
            file_mtime = 0.0
        # Small slop (2s) for clock/filesystem granularity.
        if file_mtime + 2.0 >= start_ts:
            try:
                disk_payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(disk_payload, dict):
                    payload = disk_payload
                    worker_wrote_file = True
            except Exception:
                payload = None

    if payload is None:
        # Fall back to a RESULT_JSON line the worker printed to stdout.
        if result:
            payload = dict(result)
        else:
            # Neither channel produced a result — record an explicit failure
            # rather than silently marking the run ok.
            payload = {"status": "fail", "summary": "(no RESULT_JSON emitted and no RESULT file written)"}

    payload.setdefault("task_id", task_id)
    payload.setdefault("role", req.role)
    payload.setdefault("run_id", req.run_id)
    payload.setdefault("captured_at", _now_iso())
    body = json.dumps(payload, indent=2, ensure_ascii=False)
    if not worker_wrote_file:
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
    return art_id, "result", payload


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
    # Never demote a task to CHANGES_REQUESTED on infrastructure failures.
    # If the reviewer subprocess crashed (exit != 0) without producing any
    # parseable verdict, that's a transport problem, not a work-quality
    # problem — record INDETERMINATE so the operator can re-run the review
    # cleanly without the task silently rolling back to CHANGES_REQUESTED.
    parsed = _decision_from(result, run.last_lines)
    if parsed:
        decision = parsed
    elif exit_code == 0:
        decision = "APPROVED"
    else:
        decision = "INDETERMINATE"
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
        # Approval clears any prior block reason. If a task depended on this
        # one (blocked_on=task_id), the auto-unblock hook will fire below.
        _clear_block(task_id)
        # Bundle the newly-approved task into the current pending patch so
        # the operator can see it in the "awaiting relaunch" release queue.
        try:
            from ..patches import assign_task
            assign_task(task_id)
        except Exception:
            pass
    elif decision in ("CHANGES_REQUESTED", "FAIL"):
        new_status = "CHANGES_REQUESTED"
        # Populate the "why stuck" signal from the reviewer's own output:
        # prefer RESULT.summary, fall back to the decision name.
        rsum = (result or {}).get("summary") if result else None
        reason = rsum or f"{decision} (see REVIEW_{task_id}.md)"
        _set_block(task_id, f"reviewer: {reason}")
    # INDETERMINATE / unknown → return new_status=None so finalize_run
    # leaves the task status untouched. The review artifact + row are
    # still written so the operator can see the crashed run.
    return (art_id, "review"), new_status


def _route_patch_review(req, run, exit_code) -> None:
    """Look up patch_review_meta on the runs row and dispatch."""
    row = get_conn().execute(
        "SELECT patch_review_meta FROM runs WHERE run_id=?", (req.run_id,),
    ).fetchone()
    if row is None or not row["patch_review_meta"]:
        import logging
        logging.getLogger(__name__).warning(
            "patch-review run %s has no meta — skipping orchestrator dispatch",
            req.run_id,
        )
        return
    try:
        meta = json.loads(row["patch_review_meta"])
    except Exception:
        return
    from . import patch_review as pr_mod
    patch_id = meta.get("patch_id")
    if not patch_id:
        return
    if meta.get("synthesis"):
        pr_mod.on_synthesis_finish(patch_id, req.run_id, exit_code)
    else:
        pr_mod.on_step_finish(
            patch_id,
            int(meta.get("step") or 0),
            int(meta.get("total") or 0),
            req.run_id, exit_code,
        )


def _capture_triage(req, run, exit_code) -> str | None:
    """Parse `TRIAGE: yes|no — reason` from the Sonnet triage run's stdout.

    Returns the new task status. On yes: DONE (and auto-assign to patch).
    On no or unparseable: CHANGES_REQUESTED + block_reason populated.
    """
    task_id = req.task_id
    verdict: str | None = None
    reason: str = ""
    for ln in reversed(run.last_lines):
        m = _TRIAGE_RX.match(ln)
        if m:
            verdict = m.group(1).lower()
            reason = (m.group(2) or "").strip().lstrip("—-:").strip()
            break

    if verdict == "yes" and exit_code == 0:
        _clear_block(task_id)
        try:
            from ..patches import assign_task
            assign_task(task_id)
        except Exception:
            pass
        return "DONE"
    # Anything else: park with a reason. If we couldn't even parse the
    # anchor, record that explicitly so the operator doesn't wonder why.
    display = reason if verdict == "no" and reason else (
        f"triage said no: {reason}" if reason else
        f"triage produced no TRIAGE: anchor (exit={exit_code})"
    )
    _set_block(task_id, f"triage: {display}")
    return "CHANGES_REQUESTED"


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
