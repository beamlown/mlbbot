"""Sonnet-triage auto-launcher.

Auto-fires a tiny Sonnet run against a worker's RESULT after it passes
the deterministic structural gate. The triage asks one question —
"does RESULT.summary satisfy HANDOFF.acceptance?" — and emits
`TRIAGE: yes` or `TRIAGE: no — <reason>` on its final stdout line.
The capture hook in `capture.py` parses that anchor and transitions
the task to DONE (yes) or CHANGES_REQUESTED + block_reason (no).

Triage never blocks the dispatcher: failures here (task row missing,
launch cap hit, etc.) are logged and swallowed; the task simply sits
in AWAITING_REVIEW until the operator intervenes.
"""
from __future__ import annotations

import logging
import secrets

from .base import RunRequest
from .cli_adapter import ClaudeCliAdapter
from .dispatcher import DISPATCHER
from .prompts import build_sonnet_triage_prompt
from ..db import get_conn


log = logging.getLogger(__name__)


def _new_run_id() -> str:
    return "RUN_" + secrets.token_hex(6).upper()


def launch_triage(task_id: str, worker_run_id: str) -> str | None:
    """Fire a Sonnet triage run on the latest RESULT for this task.

    Returns the new run_id on launch success, or None if we couldn't
    even start the subprocess. Reads the RESULT artifact from the DB
    (already captured by `_capture_worker` immediately before this
    call) rather than the filesystem to avoid a read/write race.
    """
    conn = get_conn()
    task_row = conn.execute(
        "SELECT * FROM tasks WHERE task_id=?", (task_id,),
    ).fetchone()
    if task_row is None:
        log.warning("triage: task %s not found", task_id)
        return None
    task = dict(task_row)

    result_row = conn.execute(
        """SELECT a.content FROM task_artifacts ta
             JOIN artifacts a ON a.artifact_id = ta.artifact_id
            WHERE ta.task_id=? AND a.kind='RESULT'
         ORDER BY a.mtime DESC LIMIT 1""",
        (task_id,),
    ).fetchone()
    result_text = (result_row["content"] if result_row else "") or ""

    prompt = build_sonnet_triage_prompt(task, result_text)

    run_id = _new_run_id()
    req = RunRequest(
        run_id=run_id,
        task_id=task_id,
        role="SONNET_TRIAGE",
        adapter="claude_cli",
        task=task,
        created_by="auto_triage",
        extra_prompt=f"triage_of_run={worker_run_id}",
    )
    adapter = ClaudeCliAdapter()
    argv = adapter.build_argv(req, prompt)
    row = DISPATCHER.launch(
        req, argv, prompt,
        stdout_transform=adapter.transform_stdout_line,
    )
    if (row or {}).get("status") == "failed":
        log.warning("triage launch failed for %s: %s",
                    task_id, (row or {}).get("result_summary"))
        return None
    return run_id
