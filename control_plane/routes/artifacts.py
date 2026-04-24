"""Artifact browser + single-artifact render."""
from __future__ import annotations

from flask import Blueprint, abort, jsonify, render_template, request

from ..db import get_conn


bp = Blueprint("artifacts", __name__)


KIND_FILTERS = (
    "ALL", "HANDOFF", "TASK", "RESULT", "REVIEW", "APPROVED",
    "PROVISIONAL_REVIEW", "SPEC", "AUDIT", "STATUS", "BOARD", "CONTEXT", "NOTE",
)


@bp.route("/artifacts/", methods=["GET"])
def list_artifacts():
    conn = get_conn()
    kind = (request.args.get("kind") or "ALL").upper()
    q = (request.args.get("q") or "").strip().lower()

    sql = "SELECT artifact_id, kind, path, title, summary, task_ref, mtime, size_bytes FROM artifacts"
    params: list = []
    filters: list[str] = []
    if kind != "ALL":
        filters.append("kind=?")
        params.append(kind)
    if q:
        filters.append("(LOWER(path) LIKE ? OR LOWER(title) LIKE ? OR LOWER(task_ref) LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    if filters:
        sql += " WHERE " + " AND ".join(filters)
    sql += " ORDER BY mtime DESC LIMIT 500"

    rows = conn.execute(sql, params).fetchall()
    artifacts = [dict(r) for r in rows]

    # Optional ?profile_id=… filter — narrow to artifacts from runs of that persona's role.
    profile_id = request.args.get("profile_id")
    if profile_id:
        prof = conn.execute(
            "SELECT role FROM agent_profiles WHERE profile_id=?", (profile_id,)
        ).fetchone()
        if prof:
            role = prof["role"]
            allowed_ids = {r["artifact_id"] for r in conn.execute(
                "SELECT DISTINCT ta.artifact_id FROM task_artifacts ta "
                "JOIN runs r ON r.task_id = ta.task_id "
                "WHERE r.role = ?", (role,)
            ).fetchall()}
            artifacts = [a for a in artifacts if a["artifact_id"] in allowed_ids]

    return render_template(
        "artifacts.html",
        artifacts=artifacts,
        kind=kind,
        kind_options=KIND_FILTERS,
        q=q,
    )


@bp.route("/artifacts/<artifact_id>", methods=["GET"])
def artifact_detail(artifact_id: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM artifacts WHERE artifact_id=?", (artifact_id,)).fetchone()
    if row is None:
        abort(404)
    return render_template("artifact.html", a=dict(row))


@bp.route("/api/artifacts/<artifact_id>/raw", methods=["GET"])
def api_artifact_raw(artifact_id: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT kind, path, content FROM artifacts WHERE artifact_id=?", (artifact_id,)
    ).fetchone()
    if row is None:
        return jsonify({"error": "not_found"}), 404
    return jsonify(dict(row))
