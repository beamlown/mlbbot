"""Derive the dashboard's workflow lane from task + artifacts + runs + reviews.

The DB's `tasks.status` remains BOT_BRIDGE-compatible
(PENDING/QUEUED/ACTIVE/BLOCKED/DONE/CHANGES_REQUESTED/ARCHIVED), but the
board UI shows derived workflow lanes that reflect the actual work state:

    READY_FOR_WORKER   — no result artifact yet; a worker can pick it up
    RUNNING            — a run is currently in flight for this task
    AWAITING_REVIEW    — result artifact exists, but no review verdict yet
    CHANGES_REQUESTED  — reviewer said the work needs changes
    DONE               — reviewer approved
    AUDIT_QUEUE        — done tasks flagged by the operator for audit
    ARCHIVED           — superseded, cancelled, or otherwise shelved

Derivation is pure — it never mutates the DB. Callers persist mutations
through the normal `actions` endpoints.
"""
from __future__ import annotations

import json
from typing import Iterable

from .db import get_conn


WORKFLOW_LANES: tuple[str, ...] = (
    "READY_FOR_WORKER",
    "RUNNING",
    "AWAITING_REVIEW",
    "CHANGES_REQUESTED",
    "DONE",
    "AUDIT_QUEUE",
    "ARCHIVED",
)


LANE_DISPLAY = {
    "READY_FOR_WORKER":  "Ready for Worker",
    "RUNNING":           "Running",
    "AWAITING_REVIEW":   "Awaiting Review",
    "CHANGES_REQUESTED": "Changes Requested",
    "DONE":              "Done",
    "AUDIT_QUEUE":       "Audit Queue",
    "ARCHIVED":          "Archived",
}


# Artifact kinds that count as a completed worker result.
_RESULT_KINDS = {"RESULT"}
# Artifact kinds that count as a review verdict.
_REVIEW_KINDS = {"REVIEW", "PROVISIONAL_REVIEW", "APPROVED"}


def _latest_review_decision(task_id: str) -> str | None:
    """Return the most recent review decision for this task, or None."""
    conn = get_conn()
    row = conn.execute(
        "SELECT decision FROM reviews WHERE task_id=? ORDER BY created_at DESC LIMIT 1",
        (task_id,),
    ).fetchone()
    if row is None:
        return None
    d = (row["decision"] or "").upper().strip()
    # Normalize a few common phrasings.
    if d.startswith("APPROV"):
        return "APPROVED"
    if d in ("CHANGES_REQUESTED", "CHANGES REQUESTED", "CHANGES", "CR"):
        return "CHANGES_REQUESTED"
    if d in ("FAIL", "FAILED", "REJECT", "REJECTED"):
        return "FAIL"
    if d in ("PROVISIONAL", "PROVISIONAL_APPROVED"):
        return "PROVISIONAL"
    return d or None


def _has_artifact_of(task_id: str, kinds: set[str]) -> bool:
    conn = get_conn()
    q_marks = ",".join("?" * len(kinds))
    row = conn.execute(
        f"""SELECT 1 FROM task_artifacts ta
              JOIN artifacts a ON a.artifact_id = ta.artifact_id
             WHERE ta.task_id=? AND a.kind IN ({q_marks}) LIMIT 1""",
        (task_id, *kinds),
    ).fetchone()
    return row is not None


def _has_active_run(task_id: str) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM runs WHERE task_id=? AND status IN ('queued','running') LIMIT 1",
        (task_id,),
    ).fetchone()
    return row is not None


def derive_state(task: dict) -> str:
    """Return the workflow lane string for this task row (dict)."""
    tid = task["task_id"]
    raw_status = (task.get("status") or "").upper()

    if raw_status == "ARCHIVED":
        return "ARCHIVED"

    if _has_active_run(tid):
        return "RUNNING"

    has_result = _has_artifact_of(tid, _RESULT_KINDS)
    has_review = _has_artifact_of(tid, _REVIEW_KINDS)
    decision = _latest_review_decision(tid)

    # Explicitly-flagged audit queue wins over DONE.
    if raw_status == "DONE" and task.get("outcome") and "AUDIT" in (task.get("outcome") or "").upper():
        return "AUDIT_QUEUE"

    if decision == "APPROVED" or raw_status == "DONE":
        return "DONE"
    if decision in ("CHANGES_REQUESTED", "FAIL") or raw_status == "CHANGES_REQUESTED":
        return "CHANGES_REQUESTED"
    # Any task with a worker result and no decided review sits in review.
    # Using `decision is None` (rather than "no REVIEW artifact exists")
    # also catches stale REVIEW artifacts left on disk with no recorded
    # decision — they should not pin the task back to READY_FOR_WORKER.
    if has_result and decision is None:
        return "AWAITING_REVIEW"
    # Default: worker can pick it up.
    return "READY_FOR_WORKER"


def annotate(task: dict) -> dict:
    """Return `task` with a `workflow_state` key set (pure copy)."""
    out = dict(task)
    out["workflow_state"] = derive_state(task)
    return out


def bucket(tasks: Iterable[dict]) -> dict[str, list[dict]]:
    """Group an iterable of task dicts into the canonical lane dict."""
    out: dict[str, list[dict]] = {lane: [] for lane in WORKFLOW_LANES}
    for t in tasks:
        a = annotate(t)
        out.setdefault(a["workflow_state"], []).append(a)
    return out


def eligible_for(agent_profile: dict, task: dict) -> bool:
    """Return True if this agent profile can act on this task right now."""
    state = task.get("workflow_state") or derive_state(task)
    try:
        allowed = json.loads(agent_profile.get("allowed_states") or "[]")
    except Exception:
        allowed = []
    return state in (allowed or [])
