"""Board + task detail + task list API."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from flask import Blueprint, abort, jsonify, render_template, request

from ..db import get_conn
from ..models import LANES, VALID_PRIORITIES, VALID_STATUSES
from ..bridge.importer import import_bot_bridge
from ..workflow import WORKFLOW_LANES, LANE_DISPLAY, derive_state


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


bp = Blueprint("tasks", __name__)


PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _task_row_dict(row) -> dict:
    d = dict(row)
    for key in ("allowed_files", "forbidden_files"):
        try:
            d[key] = json.loads(d.get(key) or "[]")
        except Exception:
            d[key] = []
    return d


def _lane_counts(conn) -> dict[str, int]:
    rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM tasks GROUP BY status"
    ).fetchall()
    return {r["status"]: r["n"] for r in rows}


@bp.route("/", methods=["GET"])
def board():
    conn = get_conn()
    q = (request.args.get("q") or "").strip().lower()
    priority = (request.args.get("priority") or "").upper() or None
    subsystem = (request.args.get("subsystem") or "").strip() or None

    base_sql = "SELECT * FROM tasks"
    params: list = []
    filters: list[str] = []
    if priority and priority in VALID_PRIORITIES:
        filters.append("priority=?")
        params.append(priority)
    if subsystem:
        filters.append("subsystem LIKE ?")
        params.append(f"%{subsystem}%")
    if q:
        filters.append("(LOWER(task_id) LIKE ? OR LOWER(title) LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    if filters:
        base_sql += " WHERE " + " AND ".join(filters)
    base_sql += " ORDER BY lane_order ASC, priority ASC, task_id ASC"

    # Patch-version annotations so DONE-lane cards can show e.g.
    # "v0.4.0 · awaiting relaunch" vs "v0.3.0 · live".
    patch_map = {
        r["patch_id"]: {"version": r["version"], "status": r["status"]}
        for r in conn.execute(
            "SELECT patch_id, version, status FROM patches"
        ).fetchall()
    }

    lanes: dict[str, list[dict]] = {lane: [] for lane in WORKFLOW_LANES}
    for row in conn.execute(base_sql, params).fetchall():
        d = _task_row_dict(row)
        d["workflow_state"] = derive_state(d)
        pid = d.get("patch_id")
        if pid and pid in patch_map:
            d["patch_info"] = patch_map[pid]
        lanes.setdefault(d["workflow_state"], []).append(d)

    for lane, items in lanes.items():
        items.sort(key=lambda t: (PRIORITY_ORDER.get(t.get("priority", "MEDIUM"), 2),
                                  t.get("lane_order", 0),
                                  t["task_id"]))

    lane_counts = {lane: len(items) for lane, items in lanes.items()}

    subsystems = [
        r["subsystem"] for r in conn.execute(
            "SELECT DISTINCT subsystem FROM tasks WHERE subsystem IS NOT NULL AND subsystem<>'' "
            "ORDER BY subsystem"
        ).fetchall()
    ]

    # Agent palette — seeded profiles used by the drag-to-launch UI.
    agents = []
    for r in conn.execute(
        "SELECT * FROM agent_profiles WHERE enabled=1 ORDER BY created_at"
    ).fetchall():
        d = dict(r)
        try:
            d["allowed_states"] = json.loads(d.get("allowed_states") or "[]")
        except Exception:
            d["allowed_states"] = []
        agents.append(d)

    return render_template(
        "board.html",
        lanes=lanes,
        lane_order=WORKFLOW_LANES,
        lane_display=LANE_DISPLAY,
        lane_counts=lane_counts,
        subsystems=subsystems,
        filter_q=q,
        filter_priority=priority or "",
        filter_subsystem=subsystem or "",
        agents=agents,
    )


@bp.route("/tasks/new", methods=["GET"])
def task_new():
    from ..roles import ROLE_INFO as _ROLES
    return render_template(
        "task_new.html",
        VALID_STATUSES=VALID_STATUSES,
        VALID_PRIORITIES=VALID_PRIORITIES,
        ROLES=_ROLES,
    )


@bp.route("/tasks/<task_id>", methods=["GET"])
def task_detail(task_id: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM tasks WHERE task_id=?", (task_id.upper(),)
    ).fetchone()
    if row is None:
        abort(404, description=f"task {task_id} not found")
    task = _task_row_dict(row)

    links = conn.execute(
        """SELECT ta.relation, a.artifact_id, a.kind, a.path, a.title, a.summary, a.mtime
             FROM task_artifacts ta
             JOIN artifacts a ON a.artifact_id = ta.artifact_id
            WHERE ta.task_id = ?
         ORDER BY CASE ta.relation
                    WHEN 'brief' THEN 0
                    WHEN 'task_json' THEN 1
                    WHEN 'result' THEN 2
                    WHEN 'review' THEN 3
                    ELSE 4 END, a.mtime DESC""",
        (task["task_id"],),
    ).fetchall()

    # Load the original HANDOFF for the collapsed "original brief" view.
    brief_content = None
    for lk in links:
        if lk["kind"] == "HANDOFF":
            art = conn.execute(
                "SELECT content FROM artifacts WHERE artifact_id=?",
                (lk["artifact_id"],),
            ).fetchone()
            if art and art["content"]:
                brief_content = art["content"]
                break

    # Load the LATEST report for this task — whichever of AUDIT, REVIEW,
    # APPROVED, PROVISIONAL_REVIEW has the newest mtime. This is what the
    # operator sees up top when opening the detail page; the original
    # HANDOFF stays available below in a collapsible section so you can
    # still read the initial brief without hunting through artifacts.
    latest_report = None
    lr_row = conn.execute(
        """SELECT a.artifact_id, a.kind, a.path, a.title, a.mtime, a.content
             FROM task_artifacts ta JOIN artifacts a ON a.artifact_id = ta.artifact_id
            WHERE ta.task_id = ?
              AND a.kind IN ('AUDIT','REVIEW','APPROVED','PROVISIONAL_REVIEW')
              AND a.content IS NOT NULL AND a.content != ''
            ORDER BY a.mtime DESC LIMIT 1""",
        (task["task_id"],),
    ).fetchone()
    if lr_row:
        latest_report = {
            "kind": lr_row["kind"],
            "title": lr_row["title"],
            "path": lr_row["path"],
            "mtime": lr_row["mtime"],
            "content": lr_row["content"],
            "artifact_id": lr_row["artifact_id"],
        }

    # Pull the most recent RESULT artifact so the detail page can render
    # a prominent status card ("ok / fail / blocked" + summary) above the
    # brief, without the operator having to open the artifact.
    result_card = None
    result_link = next((lk for lk in links if lk["relation"] == "result"), None)
    if result_link:
        art = conn.execute(
            "SELECT content, mtime FROM artifacts WHERE artifact_id=?",
            (result_link["artifact_id"],),
        ).fetchone()
        try:
            payload = json.loads(art["content"]) if art and art["content"] else {}
        except Exception:
            payload = {}
        if isinstance(payload, dict):
            status_raw = str(payload.get("status") or "").lower()
            if status_raw in ("ok", "success", "succeeded", "pass"):
                card_kind = "ok"
            elif status_raw in ("fail", "failed", "error"):
                card_kind = "fail"
            elif status_raw in ("blocked", "block", "pending"):
                card_kind = "blocked"
            else:
                card_kind = "ok" if status_raw else "unknown"
            result_card = {
                "status": payload.get("status") or "unknown",
                "status_kind": card_kind,
                "summary": payload.get("summary") or result_link["summary"],
                "run_id": payload.get("run_id"),
                "role": payload.get("role"),
                "captured_at": payload.get("captured_at"),
                "artifact_id": result_link["artifact_id"],
                "files_changed": payload.get("files_changed") or [],
                "next_steps": payload.get("next_steps") or payload.get("next_fix_targets") or [],
            }

    runs = conn.execute(
        "SELECT * FROM runs WHERE task_id=? ORDER BY created_at DESC LIMIT 20",
        (task["task_id"],),
    ).fetchall()

    reviews = conn.execute(
        "SELECT * FROM reviews WHERE task_id=? ORDER BY created_at DESC",
        (task["task_id"],),
    ).fetchall()

    task["workflow_state"] = derive_state(task)

    agents = []
    for r in conn.execute(
        "SELECT * FROM agent_profiles WHERE enabled=1 ORDER BY created_at"
    ).fetchall():
        d = dict(r)
        try:
            d["allowed_states"] = json.loads(d.get("allowed_states") or "[]")
        except Exception:
            d["allowed_states"] = []
        d["eligible"] = task["workflow_state"] in d["allowed_states"]
        agents.append(d)

    return render_template(
        "task_detail.html",
        task=task,
        links=[dict(lk) for lk in links],
        brief_content=brief_content,
        latest_report=latest_report,
        runs=[dict(r) for r in runs],
        reviews=[dict(r) for r in reviews],
        agents=agents,
        result_card=result_card,
        VALID_STATUSES=VALID_STATUSES,
    )


# ---------------------------------------------------------------------------
# JSON APIs
# ---------------------------------------------------------------------------

@bp.route("/api/tasks", methods=["GET"])
def api_list_tasks():
    conn = get_conn()
    status = (request.args.get("status") or "").upper() or None
    priority = (request.args.get("priority") or "").upper() or None
    subsystem = (request.args.get("subsystem") or "").strip() or None
    q = (request.args.get("q") or "").strip().lower()

    sql = "SELECT * FROM tasks"
    params: list = []
    filters: list[str] = []
    if status in VALID_STATUSES:
        filters.append("status=?")
        params.append(status)
    if priority in VALID_PRIORITIES:
        filters.append("priority=?")
        params.append(priority)
    if subsystem:
        filters.append("subsystem LIKE ?")
        params.append(f"%{subsystem}%")
    if q:
        filters.append("(LOWER(task_id) LIKE ? OR LOWER(title) LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    if filters:
        sql += " WHERE " + " AND ".join(filters)
    sql += " ORDER BY lane_order ASC, priority ASC LIMIT 500"

    rows = conn.execute(sql, params).fetchall()
    return jsonify([_task_row_dict(r) for r in rows])


@bp.route("/api/tasks/<task_id>", methods=["GET"])
def api_task(task_id: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM tasks WHERE task_id=?", (task_id.upper(),)
    ).fetchone()
    if row is None:
        return jsonify({"error": "not_found"}), 404
    return jsonify(_task_row_dict(row))


@bp.route("/api/import", methods=["POST"])
def api_reimport():
    report = import_bot_bridge()
    return jsonify(report.to_dict())


@bp.route("/api/import/status", methods=["GET"])
def api_import_status():
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM import_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return jsonify({"ran": False})
    return jsonify({"ran": True, **dict(row)})


# ---------------------------------------------------------------------------
# Park / unblock — "why stuck" signal + optional dependency parking.
#
# block_reason: free text, "why the task is currently stuck". Populated by
#   capture.py when a worker/reviewer/triage/structural path fails. Shown
#   on the board card so the operator stops blind-retrying.
# blocked_on:   optional task_id of the dependency. When that task reaches
#   DONE, the auto-unblock hook clears both fields.
# Launch guard: runs.py refuses to start a run on a task with EITHER field
#   set, unless force=true.
# ---------------------------------------------------------------------------

@bp.route("/api/tasks/<task_id>/park", methods=["POST"])
def api_task_park(task_id: str):
    body = request.get_json(silent=True) or {}
    blocked_on = (body.get("blocked_on") or "").strip().upper() or None
    reason = (body.get("reason") or "").strip()
    if not blocked_on and not reason:
        return jsonify({"ok": False, "error": "need blocked_on or reason"}), 400

    conn = get_conn()
    row = conn.execute(
        "SELECT task_id FROM tasks WHERE task_id=?", (task_id.upper(),),
    ).fetchone()
    if row is None:
        return jsonify({"ok": False, "error": "task_not_found"}), 404

    if blocked_on:
        dep = conn.execute(
            "SELECT task_id FROM tasks WHERE task_id=?", (blocked_on,),
        ).fetchone()
        if dep is None:
            return jsonify({"ok": False, "error": "blocker_not_found",
                            "detail": f"no such task {blocked_on}"}), 404
        if blocked_on == task_id.upper():
            return jsonify({"ok": False, "error": "cannot_self_block"}), 400

    now = _now_iso()
    display_reason = reason or f"parked behind {blocked_on}"
    conn.execute(
        "UPDATE tasks SET blocked_on=?, block_reason=?, blocked_at=?, updated_at=? "
        "WHERE task_id=?",
        (blocked_on, display_reason[:500], now, now, task_id.upper()),
    )
    return jsonify({
        "ok": True, "task_id": task_id.upper(),
        "blocked_on": blocked_on, "block_reason": display_reason,
    })


@bp.route("/api/tasks/<task_id>/park", methods=["DELETE"])
def api_task_unpark(task_id: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT task_id FROM tasks WHERE task_id=?", (task_id.upper(),),
    ).fetchone()
    if row is None:
        return jsonify({"ok": False, "error": "task_not_found"}), 404
    now = _now_iso()
    conn.execute(
        "UPDATE tasks SET blocked_on=NULL, block_reason=NULL, blocked_at=NULL, "
        "updated_at=? WHERE task_id=?",
        (now, task_id.upper()),
    )
    return jsonify({"ok": True, "task_id": task_id.upper()})


# Hard delete — used by the dashboard trash button. Refuses if the task
# has already shipped in a patch (history must remain auditable). Cascade
# drops task_artifacts + reviews via FK ON DELETE CASCADE.
@bp.route("/api/tasks/<task_id>", methods=["DELETE"])
def api_task_delete(task_id: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT t.task_id, t.patch_id, p.status AS patch_status "
        "FROM tasks t LEFT JOIN patches p ON p.patch_id = t.patch_id "
        "WHERE t.task_id=?", (task_id.upper(),),
    ).fetchone()
    if row is None:
        return jsonify({"ok": False, "error": "task_not_found"}), 404
    if row["patch_status"] == "SHIPPED":
        return jsonify({
            "ok": False, "error": "task_shipped",
            "detail": f"task is part of shipped patch {row['patch_id']}; history retained",
        }), 409
    conn.execute("DELETE FROM tasks WHERE task_id=?", (task_id.upper(),))
    return jsonify({"ok": True, "deleted": task_id.upper()})
