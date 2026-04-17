"""DB → BOT_BRIDGE filesystem exporter.

Round-trip rules (keep the prose trail intact):

- `TASK_*.json` is **machine-owned**: we overwrite freely from DB on every
  mutation. Hash-conflict check first (see `check_conflict`).
- `HANDOFF_*.md` is **prose-owned**: we only create it when it does not
  exist. Never overwritten silently. The operator's narrative is sacred.
- `CLAUDE_TASK_BOARD.md` regeneration is handled in `task_board_md.py` —
  it surgically replaces only the lane pipe-tables and leaves every
  hand-written section (prefix, policy reminders, conflict map, system
  state) untouched.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..config import SETTINGS
from ..db import get_conn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _relpath(p: Path) -> str:
    try:
        return str(p.relative_to(SETTINGS.repo_root)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

@dataclass
class ConflictReport:
    conflict: bool
    reason: str
    path: str
    disk_sha256: str | None = None
    db_hash: str | None = None


def check_conflict(task_id: str) -> ConflictReport:
    """Compare the on-disk TASK_*.json hash against the hash we last wrote.

    If they differ, someone edited the file outside the dashboard and our
    next export would overwrite their edit. The caller should either
    re-import to pull their changes in, or pass `force=True` to overwrite.
    """
    task_id = task_id.upper()
    conn = get_conn()
    row = conn.execute(
        "SELECT external_hash, brief_path FROM tasks WHERE task_id=?",
        (task_id,),
    ).fetchone()
    if row is None:
        return ConflictReport(False, "task_not_in_db", "")

    target = _task_json_path(task_id)
    if not target.exists():
        return ConflictReport(False, "new_file", _relpath(target))

    try:
        disk = target.read_bytes()
    except Exception as e:
        return ConflictReport(True, f"read_error:{e}", _relpath(target))
    disk_hash = _sha256(disk)

    if row["external_hash"] and disk_hash != row["external_hash"]:
        return ConflictReport(
            True, "external_edit_since_last_export",
            _relpath(target),
            disk_sha256=disk_hash,
            db_hash=row["external_hash"],
        )
    return ConflictReport(False, "clean", _relpath(target),
                          disk_sha256=disk_hash, db_hash=row["external_hash"])


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _inbox() -> Path:
    p = SETTINGS.bridge_root / "05_INBOX_FROM_MANAGER"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _task_json_path(task_id: str) -> Path:
    return _inbox() / f"TASK_{task_id}.json"


def _handoff_path(task_id: str) -> Path:
    return _inbox() / f"HANDOFF_{task_id}.md"


# ---------------------------------------------------------------------------
# TASK_*.json export
# ---------------------------------------------------------------------------

def export_task(task_id: str, *, force: bool = False,
                write_handoff_stub: bool = True) -> dict:
    """Write `TASK_<id>.json` from the DB row.

    Returns a dict describing what happened.
    """
    task_id = task_id.upper()
    conn = get_conn()
    row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
    if row is None:
        return {"ok": False, "error": "task_not_found"}

    conflict = check_conflict(task_id)
    if conflict.conflict and not force:
        conn.execute("UPDATE tasks SET conflict=1 WHERE task_id=?", (task_id,))
        return {
            "ok": False, "error": "conflict",
            "reason": conflict.reason,
            "path": conflict.path,
            "disk_sha256": conflict.disk_sha256,
            "db_hash": conflict.db_hash,
        }

    payload = _task_to_json(dict(row))
    raw = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
    target = _task_json_path(task_id)
    target.write_bytes(raw)

    handoff_created = False
    if write_handoff_stub:
        hp = _handoff_path(task_id)
        if not hp.exists():
            hp.write_text(_handoff_stub(payload), encoding="utf-8")
            handoff_created = True

    ext_hash = _sha256(raw)
    ext_mtime = int(target.stat().st_mtime)
    conn.execute(
        """UPDATE tasks SET external_hash=?, external_mtime=?, conflict=0,
                            brief_path=COALESCE(brief_path, ?), updated_at=?
            WHERE task_id=?""",
        (ext_hash, ext_mtime, f"05_INBOX_FROM_MANAGER/HANDOFF_{task_id}.md",
         _now_iso(), task_id),
    )

    return {
        "ok": True,
        "path": _relpath(target),
        "sha256": ext_hash,
        "handoff_created": handoff_created,
        "handoff_path": _relpath(_handoff_path(task_id)) if handoff_created else None,
    }


def _task_to_json(row: dict) -> dict:
    allowed = _loadlist(row.get("allowed_files"))
    forbidden = _loadlist(row.get("forbidden_files"))
    out = {
        "task_id": row["task_id"],
        "type": row.get("type") or "unspecified",
        "priority": row.get("priority") or "MEDIUM",
        "status": row.get("status") or "PENDING",
        "issued": row.get("issued") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "subsystem": row.get("subsystem") or "",
        "title": row.get("title") or row["task_id"],
        "allowed_files": allowed,
        "forbidden_files": forbidden,
        "brief_path": row.get("brief_path") or f"05_INBOX_FROM_MANAGER/HANDOFF_{row['task_id']}.md",
    }
    if row.get("result_path"):
        out["result_path"] = row["result_path"]
    if row.get("review_path"):
        out["review_path"] = row["review_path"]
    if row.get("assigned_role"):
        out["assigned_role"] = row["assigned_role"]
    if row.get("acceptance"):
        out["acceptance"] = row["acceptance"]
    if row.get("evidence"):
        out["evidence"] = row["evidence"]
    return out


def _loadlist(s) -> list[str]:
    if not s:
        return []
    try:
        v = json.loads(s) if isinstance(s, str) else s
        return v if isinstance(v, list) else []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# HANDOFF_*.md stub writer (used only when the file does not exist)
# ---------------------------------------------------------------------------

def _handoff_stub(payload: dict) -> str:
    allowed = payload.get("allowed_files") or []
    forbidden = payload.get("forbidden_files") or []
    lines = [
        f"# HANDOFF_{payload['task_id']}",
        "",
        f"## Status: {payload.get('status', 'PENDING')}",
        "",
        f"**Title**: {payload.get('title', '')}",
        f"**Priority**: {payload.get('priority', 'MEDIUM')}",
        f"**Subsystem**: {payload.get('subsystem') or '(unspecified)'}",
        f"**Issued**: {payload.get('issued', '')}",
    ]
    if payload.get("assigned_role"):
        lines.append(f"**Assigned**: {payload['assigned_role']}")
    lines += ["", "---", "", "## What this task is", "", "_(edit me — auto-generated stub)_", ""]
    lines.append("## Allowed files")
    lines += [f"- `{f}`" for f in allowed] or ["- _(none specified)_"]
    if forbidden:
        lines += ["", "## Forbidden files"] + [f"- `{f}`" for f in forbidden]
    if payload.get("acceptance"):
        lines += ["", "## Acceptance", "", payload["acceptance"]]
    if payload.get("evidence"):
        lines += ["", "## Evidence", "", payload["evidence"]]
    lines += ["", "---", "",
              "_Auto-generated stub. Replace with narrative brief; the dashboard "
              "will not overwrite this file once it exists._", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Re-hash a file we just wrote and record it in the DB — handy for tests
# ---------------------------------------------------------------------------

def recompute_external_hash(task_id: str) -> str | None:
    target = _task_json_path(task_id.upper())
    if not target.exists():
        return None
    h = _sha256(target.read_bytes())
    get_conn().execute(
        "UPDATE tasks SET external_hash=?, external_mtime=?, updated_at=? WHERE task_id=?",
        (h, int(target.stat().st_mtime), _now_iso(), task_id.upper()),
    )
    return h
