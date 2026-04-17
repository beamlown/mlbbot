"""Mutation routes — Phase 2.

All mutations:
1. Validate input.
2. Write to DB inside a transaction.
3. Export TASK_*.json back to 05_INBOX_FROM_MANAGER (conflict-guarded).
4. Regenerate CLAUDE_TASK_BOARD.md when lane / status / order changes.

Every endpoint returns JSON `{ok: true|false, ...}` so the frontend can
surface errors cleanly.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from ..db import get_conn, tx
from ..models import LANES, VALID_PRIORITIES, VALID_STATUSES
from ..roles import ROLE_INFO
from ..bridge.exporter import export_task, check_conflict
from ..bridge.task_board_md import regenerate_board_md


bp = Blueprint("actions", __name__)


TASK_ID_RX = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_body() -> dict:
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form.to_dict(flat=True)


def _loadlist(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    if isinstance(v, str):
        # Accept JSON array, comma-separated, or newline-separated.
        s = v.strip()
        if not s:
            return []
        if s.startswith("["):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed if str(x).strip()]
            except Exception:
                pass
        parts = re.split(r"[,\n]", s)
        return [p.strip() for p in parts if p.strip()]
    return []


def _normalize_task_id(tid: str) -> str | None:
    tid = (tid or "").strip().upper().replace("-", "_").replace(" ", "_")
    if not TASK_ID_RX.match(tid):
        return None
    return tid


def _touched(task_id: str, *, regenerate_board: bool = True,
             export: bool = True, force: bool = False) -> dict:
    """Export the single task's JSON + (optionally) regenerate the board."""
    out: dict = {"task_id": task_id, "export": None, "board": None}
    if export:
        out["export"] = export_task(task_id, force=force)
    if regenerate_board:
        try:
            out["board"] = regenerate_board_md()
        except Exception as e:
            out["board"] = {"ok": False, "error": repr(e)}
    return out


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------

@bp.route("/api/tasks", methods=["POST"])
def api_create_task():
    body = _json_body()
    tid = _normalize_task_id(body.get("task_id", ""))
    if not tid:
        return jsonify({"ok": False, "error": "invalid_task_id",
                        "hint": "Use UPPERCASE letters, digits, underscore."}), 400
    title = (body.get("title") or "").strip()
    if not title:
        return jsonify({"ok": False, "error": "title_required"}), 400
    priority = (body.get("priority") or "MEDIUM").upper()
    if priority not in VALID_PRIORITIES:
        priority = "MEDIUM"
    status = (body.get("status") or "QUEUED").upper()
    if status not in VALID_STATUSES:
        status = "QUEUED"
    subsystem = (body.get("subsystem") or "").strip() or None
    notes = (body.get("notes") or "").strip() or None
    acceptance = (body.get("acceptance") or "").strip() or None
    assigned_role = (body.get("assigned_role") or "").strip().upper() or None
    if assigned_role and assigned_role not in ROLE_INFO:
        return jsonify({"ok": False, "error": "invalid_role"}), 400
    allowed = _loadlist(body.get("allowed_files"))
    forbidden = _loadlist(body.get("forbidden_files"))

    conn = get_conn()
    exists = conn.execute("SELECT 1 FROM tasks WHERE task_id=?", (tid,)).fetchone()
    if exists:
        return jsonify({"ok": False, "error": "task_id_taken"}), 409

    now = _now_iso()
    with tx() as c:
        c.execute(
            """INSERT INTO tasks
               (task_id, type, priority, status, issued, subsystem, title,
                allowed_files, forbidden_files, acceptance, notes,
                assigned_role, brief_path, source, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                tid, body.get("type") or "manual",
                priority, status,
                datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                subsystem, title,
                json.dumps(allowed),
                json.dumps(forbidden),
                acceptance, notes, assigned_role,
                f"05_INBOX_FROM_MANAGER/HANDOFF_{tid}.md",
                "dashboard", now, now,
            ),
        )

    return jsonify({"ok": True, "task_id": tid, **_touched(tid)})


# ---------------------------------------------------------------------------
# PATCH — edit fields
# ---------------------------------------------------------------------------

EDITABLE_FIELDS = {
    "title", "priority", "subsystem", "acceptance", "notes",
    "allowed_files", "forbidden_files", "evidence", "type",
}


@bp.route("/api/tasks/<task_id>", methods=["PATCH"])
def api_edit_task(task_id: str):
    tid = _normalize_task_id(task_id)
    if not tid:
        return jsonify({"ok": False, "error": "invalid_task_id"}), 400
    body = _json_body()
    conn = get_conn()
    row = conn.execute("SELECT task_id FROM tasks WHERE task_id=?", (tid,)).fetchone()
    if row is None:
        return jsonify({"ok": False, "error": "not_found"}), 404

    sets: list[str] = []
    args: list = []
    for key, val in body.items():
        if key not in EDITABLE_FIELDS:
            continue
        if key in ("allowed_files", "forbidden_files"):
            args.append(json.dumps(_loadlist(val)))
        elif key == "priority":
            p = (val or "").upper()
            args.append(p if p in VALID_PRIORITIES else "MEDIUM")
        else:
            v = (str(val).strip() if val is not None else None)
            args.append(v or None)
        sets.append(f"{key}=?")
    if not sets:
        return jsonify({"ok": False, "error": "no_editable_fields_supplied"}), 400
    sets.append("updated_at=?")
    args.append(_now_iso())
    args.append(tid)
    with tx() as c:
        c.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE task_id=?", args)

    return jsonify({"ok": True, **_touched(tid)})


# ---------------------------------------------------------------------------
# TRANSITION — change status / lane_order
# ---------------------------------------------------------------------------

@bp.route("/api/tasks/<task_id>/transition", methods=["POST"])
def api_transition(task_id: str):
    tid = _normalize_task_id(task_id)
    if not tid:
        return jsonify({"ok": False, "error": "invalid_task_id"}), 400
    body = _json_body()
    new_status = (body.get("status") or "").upper()
    if new_status not in VALID_STATUSES:
        return jsonify({"ok": False, "error": "invalid_status",
                        "valid": list(VALID_STATUSES)}), 400
    lane_order = body.get("lane_order")
    if lane_order is not None:
        try:
            lane_order = int(lane_order)
        except Exception:
            lane_order = None

    conn = get_conn()
    row = conn.execute("SELECT task_id, status FROM tasks WHERE task_id=?", (tid,)).fetchone()
    if row is None:
        return jsonify({"ok": False, "error": "not_found"}), 404

    now = _now_iso()
    with tx() as c:
        if lane_order is not None:
            c.execute(
                "UPDATE tasks SET status=?, lane_order=?, updated_at=? WHERE task_id=?",
                (new_status, lane_order, now, tid),
            )
        else:
            c.execute(
                "UPDATE tasks SET status=?, updated_at=? WHERE task_id=?",
                (new_status, now, tid),
            )
    return jsonify({"ok": True, "from": row["status"], "to": new_status, **_touched(tid)})


# ---------------------------------------------------------------------------
# REORDER — change lane_order in bulk (drag-drop within a lane)
# ---------------------------------------------------------------------------

@bp.route("/api/board/reorder", methods=["POST"])
def api_reorder():
    """
    Body: {"lane": "ACTIVE", "order": ["TID_A","TID_B","TID_C"]}
    Sets status=lane and lane_order=index for every id, then regenerates
    board.md once.
    """
    body = _json_body()
    lane = (body.get("lane") or "").upper()
    if lane not in LANES:
        return jsonify({"ok": False, "error": "invalid_lane"}), 400
    order = body.get("order") or []
    if not isinstance(order, list):
        return jsonify({"ok": False, "error": "order_must_be_list"}), 400
    now = _now_iso()
    missing: list[str] = []
    updated: list[str] = []
    conn = get_conn()
    with tx() as c:
        for i, raw_tid in enumerate(order):
            tid = _normalize_task_id(str(raw_tid))
            if not tid:
                continue
            exists = c.execute("SELECT 1 FROM tasks WHERE task_id=?", (tid,)).fetchone()
            if not exists:
                missing.append(tid)
                continue
            c.execute(
                "UPDATE tasks SET status=?, lane_order=?, updated_at=? WHERE task_id=?",
                (lane, i, now, tid),
            )
            updated.append(tid)

    # Export every moved task + regenerate board once.
    per_task_results = []
    for tid in updated:
        per_task_results.append({"task_id": tid, "export": export_task(tid)})
    board_res = {}
    try:
        board_res = regenerate_board_md()
    except Exception as e:
        board_res = {"ok": False, "error": repr(e)}
    return jsonify({
        "ok": True, "lane": lane, "moved": updated, "missing": missing,
        "per_task": per_task_results, "board": board_res,
    })


# ---------------------------------------------------------------------------
# ASSIGN — set the assigned_role
# ---------------------------------------------------------------------------

@bp.route("/api/tasks/<task_id>/assign", methods=["POST"])
def api_assign(task_id: str):
    tid = _normalize_task_id(task_id)
    if not tid:
        return jsonify({"ok": False, "error": "invalid_task_id"}), 400
    body = _json_body()
    role = (body.get("assigned_role") or body.get("role") or "").upper() or None
    if role and role not in ROLE_INFO:
        return jsonify({"ok": False, "error": "invalid_role",
                        "valid": list(ROLE_INFO.keys())}), 400
    conn = get_conn()
    row = conn.execute("SELECT task_id FROM tasks WHERE task_id=?", (tid,)).fetchone()
    if row is None:
        return jsonify({"ok": False, "error": "not_found"}), 404
    now = _now_iso()
    with tx() as c:
        c.execute(
            "UPDATE tasks SET assigned_role=?, updated_at=? WHERE task_id=?",
            (role, now, tid),
        )
    return jsonify({"ok": True, "assigned_role": role, **_touched(tid, regenerate_board=False)})


# ---------------------------------------------------------------------------
# EXPORT — manual "export this task" button
# ---------------------------------------------------------------------------

@bp.route("/api/tasks/<task_id>/export", methods=["POST"])
def api_export(task_id: str):
    tid = _normalize_task_id(task_id)
    if not tid:
        return jsonify({"ok": False, "error": "invalid_task_id"}), 400
    force = bool(_json_body().get("force"))
    res = export_task(tid, force=force)
    board = {}
    if res.get("ok"):
        try:
            board = regenerate_board_md()
        except Exception as e:
            board = {"ok": False, "error": repr(e)}
    return jsonify({"task_id": tid, "export": res, "board": board})


@bp.route("/api/tasks/<task_id>/conflict", methods=["GET"])
def api_check_conflict(task_id: str):
    tid = _normalize_task_id(task_id)
    if not tid:
        return jsonify({"ok": False, "error": "invalid_task_id"}), 400
    c = check_conflict(tid)
    return jsonify({
        "ok": True, "task_id": tid, "conflict": c.conflict, "reason": c.reason,
        "path": c.path, "disk_sha256": c.disk_sha256, "db_hash": c.db_hash,
    })


@bp.route("/api/board/regenerate", methods=["POST"])
def api_regenerate_board():
    try:
        res = regenerate_board_md()
        return jsonify({"ok": True, **res})
    except Exception as e:
        return jsonify({"ok": False, "error": repr(e)}), 500


# ---------------------------------------------------------------------------
# SETTINGS — switch acting role (used by the top-bar dropdown)
# ---------------------------------------------------------------------------

@bp.route("/api/settings/acting_role", methods=["POST"])
def api_set_acting_role():
    body = _json_body()
    role = (body.get("role") or "").upper()
    if role not in ROLE_INFO:
        return jsonify({"ok": False, "error": "invalid_role"}), 400
    now = _now_iso()
    with tx() as c:
        c.execute(
            "INSERT INTO settings(key, value, updated_at, updated_by) VALUES(?,?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            ("acting_role", role, now, "dashboard"),
        )
    return jsonify({"ok": True, "acting_role": role})
