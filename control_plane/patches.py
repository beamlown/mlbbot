"""Release-patch bundling for the control plane.

The operator's mental model:

    Tasks that reach DONE (reviewer approved) are not yet LIVE in
    the running bot. They are queued into a PENDING patch. When the
    operator relaunches the bot process they "ship" the patch, which
    bumps the version and creates a new empty pending patch. Tasks
    that were in the now-shipped patch become part of the bot's live
    version history.

States:
    PENDING  — being assembled; new approvals land here
    SHIPPED  — versioned, deployed; immutable

This module intentionally stays small. It exposes:
    - `ensure_pending_patch()` -> dict            (create-or-fetch the open patch)
    - `assign_task(task_id)` -> str               (attach a task to the pending patch)
    - `ship_pending(title=None)` -> dict          (freeze + bump version)
    - `list_patches(include_pending=True)` -> [dict]
    - `get_patch(patch_id)` -> dict | None
    - `tasks_in_patch(patch_id)` -> [dict]
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from .db import get_conn


_SEMVER_RX = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _next_version(prev: str | None) -> str:
    """Minor-bump `prev` (e.g. v0.3.2 -> v0.4.0). Default floor v0.1.0."""
    if not prev:
        return "v0.1.0"
    m = _SEMVER_RX.match(prev.strip())
    if not m:
        return "v0.1.0"
    major, minor, _patch = (int(x) for x in m.groups())
    return f"v{major}.{minor + 1}.0"


def _latest_shipped_version() -> str | None:
    """Return the latest shipped version that actually parses as semver.

    A non-semver version (e.g. smoke-test artifacts like 'v0.0.0-smoke')
    would bounce _next_version back to its default 'v0.1.0' — which then
    collides with the pre-existing v0.1.0 row on INSERT. Filter to valid
    semver so the version cursor is monotonic regardless of what junk
    shipped on the side.
    """
    rows = get_conn().execute(
        "SELECT version FROM patches WHERE status='SHIPPED' "
        "ORDER BY shipped_at DESC"
    ).fetchall()
    for r in rows:
        if _SEMVER_RX.match((r["version"] or "").strip()):
            return r["version"]
    return None


def ensure_pending_patch() -> dict:
    """Return the current PENDING patch, creating one if none exists."""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM patches WHERE status='PENDING' "
        "ORDER BY created_at ASC LIMIT 1"
    ).fetchone()
    if row:
        return dict(row)

    version = _next_version(_latest_shipped_version())
    patch_id = f"PATCH_{version.replace('.', '_').replace('v', 'V')}"
    now = _now_iso()
    conn.execute(
        "INSERT INTO patches(patch_id, version, status, title, notes, created_at) "
        "VALUES (?, ?, 'PENDING', ?, ?, ?)",
        (patch_id, version, f"Patch {version}", "", now),
    )
    row = conn.execute(
        "SELECT * FROM patches WHERE patch_id=?", (patch_id,)
    ).fetchone()
    return dict(row)


def assign_task(task_id: str) -> str:
    """Attach `task_id` to the pending patch. Returns the patch_id.

    Idempotent — re-attaching a task that's already on the pending patch
    is a no-op. If the task is already on a SHIPPED patch we leave it
    alone; a task can't migrate backwards out of history.
    """
    conn = get_conn()
    row = conn.execute(
        """SELECT t.patch_id AS current_patch, p.status AS current_status
             FROM tasks t
             LEFT JOIN patches p ON p.patch_id = t.patch_id
            WHERE t.task_id=?""",
        (task_id,),
    ).fetchone()
    if row and row["current_status"] == "SHIPPED":
        return row["current_patch"]

    pending = ensure_pending_patch()
    if row and row["current_patch"] == pending["patch_id"]:
        return pending["patch_id"]

    conn.execute(
        "UPDATE tasks SET patch_id=?, updated_at=? WHERE task_id=?",
        (pending["patch_id"], _now_iso(), task_id),
    )
    return pending["patch_id"]


def unassign_task(task_id: str) -> None:
    """Drop a task from its pending patch (used when a review gets retracted).

    Safe no-op if the task is not attached, or is attached to a shipped patch
    (we never mutate shipped history from here).
    """
    conn = get_conn()
    row = conn.execute(
        """SELECT t.patch_id AS current_patch, p.status AS current_status
             FROM tasks t
             LEFT JOIN patches p ON p.patch_id = t.patch_id
            WHERE t.task_id=?""",
        (task_id,),
    ).fetchone()
    if not row or not row["current_patch"]:
        return
    if row["current_status"] == "SHIPPED":
        return
    conn.execute(
        "UPDATE tasks SET patch_id=NULL, updated_at=? WHERE task_id=?",
        (_now_iso(), task_id),
    )


def ship_pending(title: str | None = None, notes: str | None = None) -> dict | None:
    """Mark the current pending patch as SHIPPED and open a new empty one.

    Returns the now-shipped patch dict, or None if there was no pending
    patch (or the pending patch had no tasks — we don't ship empty
    patches because that would just churn version numbers).
    """
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM patches WHERE status='PENDING' "
        "ORDER BY created_at ASC LIMIT 1"
    ).fetchone()
    if not row:
        return None

    pending = dict(row)
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM tasks WHERE patch_id=?",
        (pending["patch_id"],),
    ).fetchone()["n"]
    if count == 0:
        return None

    now = _now_iso()
    conn.execute(
        "UPDATE patches SET status='SHIPPED', shipped_at=?, title=?, notes=? "
        "WHERE patch_id=?",
        (now,
         (title or pending.get("title") or f"Patch {pending['version']}"),
         (notes if notes is not None else pending.get("notes") or ""),
         pending["patch_id"]),
    )

    # Seed the next empty pending patch so the board always has a
    # destination for the next approved task.
    ensure_pending_patch()

    shipped = conn.execute(
        "SELECT * FROM patches WHERE patch_id=?", (pending["patch_id"],)
    ).fetchone()
    return dict(shipped)


def list_patches(include_pending: bool = True) -> list[dict]:
    conn = get_conn()
    if include_pending:
        rows = conn.execute(
            "SELECT * FROM patches ORDER BY "
            "CASE status WHEN 'PENDING' THEN 0 ELSE 1 END, "
            "CASE WHEN shipped_at IS NULL THEN 1 ELSE 0 END, "
            "shipped_at DESC, created_at DESC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM patches WHERE status='SHIPPED' "
            "ORDER BY shipped_at DESC"
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["task_count"] = conn.execute(
            "SELECT COUNT(*) AS n FROM tasks WHERE patch_id=?", (d["patch_id"],)
        ).fetchone()["n"]
        out.append(d)
    return out


def get_patch(patch_id: str) -> dict | None:
    row = get_conn().execute(
        "SELECT * FROM patches WHERE patch_id=?", (patch_id,)
    ).fetchone()
    return dict(row) if row else None


def tasks_in_patch(patch_id: str) -> list[dict]:
    # Sort by review order (manual drag from patch detail) first, then
    # recency. block_reason/blocked_on surface on the patch_detail
    # template so the operator sees why a task can't be reviewed yet.
    rows = get_conn().execute(
        "SELECT task_id, title, status, priority, subsystem, updated_at, "
        "patch_order, blocked_on, block_reason, blocked_at "
        "FROM tasks WHERE patch_id=? "
        "ORDER BY patch_order ASC, updated_at DESC",
        (patch_id,),
    ).fetchall()
    return [dict(r) for r in rows]
