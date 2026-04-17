"""Board + task detail + task list API."""
from __future__ import annotations

import json

from flask import Blueprint, abort, jsonify, render_template, request

from ..db import get_conn
from ..models import LANES, VALID_PRIORITIES, VALID_STATUSES
from ..bridge.importer import import_bot_bridge
from ..workflow import WORKFLOW_LANES, LANE_DISPLAY, derive_state


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

    lanes: dict[str, list[dict]] = {lane: [] for lane in WORKFLOW_LANES}
    for row in conn.execute(base_sql, params).fetchall():
        d = _task_row_dict(row)
        d["workflow_state"] = derive_state(d)
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

    # Load the brief content inline if we have one (first HANDOFF we find).
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
        runs=[dict(r) for r in runs],
        reviews=[dict(r) for r in reviews],
        agents=agents,
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
