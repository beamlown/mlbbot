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
from typing import Iterable, Optional

from .db import get_conn


WORKFLOW_LANES: tuple[str, ...] = (
    "DRAFT",
    "READY_FOR_WORKER",
    "RUNNING",
    "AWAITING_REVIEW",
    "CHANGES_REQUESTED",
    "BLOCKED",
    "DONE",
    "LIVE",
    "AUDIT_QUEUE",
    "ARCHIVED",
)


LANE_DISPLAY = {
    "DRAFT":             "On Deck",
    "READY_FOR_WORKER":  "At Bat",
    "RUNNING":           "In Play",
    "AWAITING_REVIEW":   "Close Play",
    "CHANGES_REQUESTED": "Foul Ball",
    "BLOCKED":           "Rain Delay",
    "DONE":              "Safe",
    "LIVE":              "In The Books",
    "AUDIT_QUEUE":       "Bullpen",
    "ARCHIVED":          "Trophy Case",
}

# Lanes that render on the loop-back row rather than the main strip.
LOOPBACK_LANES: tuple[str, ...] = ("CHANGES_REQUESTED",)

# Lanes considered "in-flight" for stale detection.
IN_FLIGHT_LANES: frozenset[str] = frozenset(
    {"READY_FOR_WORKER", "AWAITING_REVIEW", "CHANGES_REQUESTED"}
)


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


def _patch_status_for(task_id: str) -> Optional[str]:
    """Return uppercased patches.status for this task's assigned patch,
    or None if the task isn't in any patch. `SHIPPED` means the change is
    live in the user's deployed environment; anything else (or None) means
    it's not yet out."""
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT p.status FROM tasks t
                 JOIN patches p ON p.patch_id = t.patch_id
                WHERE t.task_id=? LIMIT 1""",
            (task_id,),
        ).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    return (row["status"] or "").upper() or None


def _is_in_shipped_patch(task_id: str) -> bool:
    return _patch_status_for(task_id) == "SHIPPED"


def _latest_result_status(task_id: str) -> Optional[str]:
    """Return the lowercased `status` field from the most recent RESULT
    artifact for this task, or None if no RESULT exists / it's unparseable.

    Worker payloads use status ∈ {ok, fail, blocked}. This lets
    derive_state distinguish a real completion from a launcher-written
    fail stub that just proves the worker produced nothing.
    """
    conn = get_conn()
    row = conn.execute(
        """SELECT a.content FROM task_artifacts ta
             JOIN artifacts a ON a.artifact_id = ta.artifact_id
            WHERE ta.task_id=? AND a.kind='RESULT'
            ORDER BY a.mtime DESC LIMIT 1""",
        (task_id,),
    ).fetchone()
    if row is None or not row["content"]:
        return None
    try:
        payload = json.loads(row["content"])
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    s = (payload.get("status") or "").strip().lower()
    return s or None


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

    # BLOCKED takes precedence over READY_FOR_WORKER / AWAITING_REVIEW.
    # Either explicit status or a non-empty block_reason marks it.
    if raw_status == "BLOCKED" or (task.get("block_reason") or "").strip():
        return "BLOCKED"

    has_result = _has_artifact_of(tid, _RESULT_KINDS)
    has_review = _has_artifact_of(tid, _REVIEW_KINDS)
    decision = _latest_review_decision(tid)

    # DRAFT: pre-promotion. The task exists in the DB but no HANDOFF artifact
    # has been exported to 05_INBOX yet. raw_status=PENDING + no HANDOFF
    # distinguishes this from READY_FOR_WORKER which requires an inbox file.
    if raw_status in ("DRAFT", "PENDING") and not _has_artifact_of(tid, {"HANDOFF"}):
        if not has_result and decision is None:
            return "DRAFT"

    # Explicitly-flagged audit queue wins over DONE.
    if raw_status == "DONE" and task.get("outcome") and "AUDIT" in (task.get("outcome") or "").upper():
        return "AUDIT_QUEUE"

    if decision == "APPROVED" or raw_status == "DONE":
        # A DONE task splits into three buckets so the operator can tell at
        # a glance what's deployed vs what's only staged vs what's just old
        # historical completion:
        #   - SHIPPED patch  → LIVE        (running in production)
        #   - PENDING patch  → DONE        (staged for next release)
        #   - no patch       → ARCHIVED    (historical, no action needed)
        p = _patch_status_for(tid)
        if p == "SHIPPED":
            return "LIVE"
        if p is None:
            return "ARCHIVED"
        return "DONE"
    if decision in ("CHANGES_REQUESTED", "FAIL") or raw_status == "CHANGES_REQUESTED":
        return "CHANGES_REQUESTED"
    # Any task with a worker result and no decided review sits in review —
    # but only if the worker actually produced an `ok` payload. A `fail` or
    # `blocked` RESULT (including launcher-written "no RESULT emitted" stubs)
    # should go to CHANGES_REQUESTED so the Awaiting Review lane reflects
    # work a reviewer can actually sign off on.
    if has_result and decision is None:
        worker_status = _latest_result_status(tid)
        if worker_status in ("fail", "blocked"):
            return "CHANGES_REQUESTED"
        return "AWAITING_REVIEW"
    # Default: worker can pick it up.
    return "READY_FOR_WORKER"


_NEW_TASK_WINDOW_SECONDS: float = 2 * 60 * 60       # 2 hours
_STALE_TASK_WINDOW_SECONDS: float = 2 * 24 * 60 * 60  # 2 days


def _parse_iso(value: str | None) -> float | None:
    if not value:
        return None
    from datetime import datetime
    try:
        # Accept both "...Z" and "+00:00" suffixes.
        v = value.rstrip("Z")
        return datetime.fromisoformat(v).timestamp()
    except Exception:
        return None


def derive_age_bucket(task: dict, state: str | None = None) -> str:
    """Classify the task's freshness for the board UI.

    Returns one of:
      "new"    — first seen in the last 2 hours
      "stale"  — sitting in an in-flight lane for more than 2 days with
                 no transition
      "active" — anything else
    """
    import time as _t
    now = _t.time()
    first_seen = _parse_iso(task.get("age_first_seen")) or _parse_iso(task.get("created_at"))
    if first_seen is not None and (now - first_seen) <= _NEW_TASK_WINDOW_SECONDS:
        return "new"
    last_trans = _parse_iso(task.get("last_transition_ts")) or _parse_iso(task.get("updated_at"))
    st = (state or task.get("workflow_state") or derive_state(task))
    if (
        last_trans is not None
        and st in IN_FLIGHT_LANES
        and (now - last_trans) > _STALE_TASK_WINDOW_SECONDS
    ):
        return "stale"
    return "active"


def _extract_track(task: dict) -> str | None:
    """Best-effort extract TRACK: A|B from the HANDOFF content.

    Looks up the most recent HANDOFF artifact linked to this task and
    scans its first 40 lines for a `TRACK:` declaration. Returns "A",
    "B", or None.
    """
    tid = task.get("task_id")
    if not tid:
        return None
    conn = get_conn()
    row = conn.execute(
        """SELECT a.content FROM task_artifacts ta
             JOIN artifacts a ON a.artifact_id = ta.artifact_id
            WHERE ta.task_id=? AND a.kind='HANDOFF'
            ORDER BY a.mtime DESC LIMIT 1""",
        (tid,),
    ).fetchone()
    if not row or not row["content"]:
        return None
    for line in (row["content"] or "").splitlines()[:40]:
        stripped = line.strip()
        if stripped.upper().startswith("TRACK:"):
            val = stripped.split(":", 1)[1].strip().upper()
            if val in ("A", "B"):
                return val
            return None
    return None


def annotate(task: dict) -> dict:
    """Return `task` with `workflow_state`, `age_bucket`, `attempt_num`,
    and `track` keys set (pure copy)."""
    out = dict(task)
    state = derive_state(task)
    out["workflow_state"] = state
    out["age_bucket"] = derive_age_bucket(task, state)
    try:
        attempt = int(task.get("attempt") or 1)
    except (TypeError, ValueError):
        attempt = 1
    out["attempt_num"] = max(1, attempt)
    out["track"] = _extract_track(task)
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
