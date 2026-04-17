"""HTTP routes for the patch / version release queue."""
from __future__ import annotations

from flask import Blueprint, abort, jsonify, render_template, request

from .. import patches as patch_svc


bp = Blueprint("patches", __name__)


@bp.route("/patches", methods=["GET"])
def patches_index():
    """Release queue: pending patch on top, shipped history below."""
    all_patches = patch_svc.list_patches(include_pending=True)
    # Always show an open pending patch at the top, even when empty.
    if not any(p["status"] == "PENDING" for p in all_patches):
        patch_svc.ensure_pending_patch()
        all_patches = patch_svc.list_patches(include_pending=True)
    pending = next((p for p in all_patches if p["status"] == "PENDING"), None)
    shipped = [p for p in all_patches if p["status"] == "SHIPPED"]
    pending_tasks = patch_svc.tasks_in_patch(pending["patch_id"]) if pending else []
    return render_template(
        "patches.html",
        pending=pending,
        pending_tasks=pending_tasks,
        shipped=shipped,
    )


@bp.route("/patches/<patch_id>", methods=["GET"])
def patch_detail(patch_id: str):
    patch = patch_svc.get_patch(patch_id)
    if not patch:
        abort(404, description=f"patch {patch_id} not found")
    tasks = patch_svc.tasks_in_patch(patch_id)
    return render_template("patch_detail.html", patch=patch, tasks=tasks)


# ------------------------------------------------------------------ JSON APIs


@bp.route("/api/patches", methods=["GET"])
def api_list_patches():
    return jsonify({"ok": True, "patches": patch_svc.list_patches(True)})


@bp.route("/api/patches/ship", methods=["POST"])
def api_ship_patch():
    """Freeze the pending patch, bump the version, start a new pending one."""
    body = request.get_json(silent=True) or {}
    title = body.get("title") or None
    notes = body.get("notes")
    shipped = patch_svc.ship_pending(title=title, notes=notes)
    if shipped is None:
        return jsonify({
            "ok": False,
            "error": "nothing_to_ship",
            "detail": "The pending patch is empty — approve at least one task first.",
        }), 409
    new_pending = patch_svc.ensure_pending_patch()
    return jsonify({
        "ok": True,
        "shipped": shipped,
        "next_pending": new_pending,
    })


# ---------------------------------------------------------------------------
# Patch-level Opus review (sole Opus gate before ship).
#
# Sequential per-task review with TL;DRs carried forward between steps,
# then one synthesis run rendering the overall SHIP/CHANGES_REQUESTED/
# BLOCK verdict. Orchestration lives in runner/patch_review.py; these
# endpoints are the thin operator-facing surface.
# ---------------------------------------------------------------------------

@bp.route("/api/patches/<patch_id>/review", methods=["POST"])
def api_patch_review_start(patch_id: str):
    from ..runner.patch_review import start as _start
    result = _start(patch_id)
    if not result.get("ok"):
        err = result.get("error")
        # 404 for missing patch; 409 for already-running or empty/blocked.
        if err == "patch_not_found":
            return jsonify(result), 404
        if err in ("already_running", "blocked_tasks", "empty_patch", "launch_failed"):
            code = 409 if err == "already_running" else 400
            return jsonify(result), code
        return jsonify(result), 500
    return jsonify(result), 202


@bp.route("/api/patches/<patch_id>/review", methods=["GET"])
def api_patch_review_status(patch_id: str):
    from ..db import get_conn
    row = get_conn().execute(
        "SELECT * FROM patch_reviews WHERE patch_id=?", (patch_id,),
    ).fetchone()
    if row is None:
        return jsonify({"ok": True, "state": "never_run", "patch_id": patch_id})
    import json as _json
    d = dict(row)
    for k in ("summaries_json", "run_ids_json", "failed_steps_json"):
        try:
            d[k] = _json.loads(d.get(k) or "[]")
        except Exception:
            d[k] = []
    return jsonify({"ok": True, "state": d["status"], "review": d})


@bp.route("/api/patches/<patch_id>/order", methods=["PATCH"])
def api_patch_reorder(patch_id: str):
    """Body: {order: ["TASK_A","TASK_B", ...]} — positional review order.

    Writes 0-based patch_order per task. Unknown task_ids are ignored;
    tasks in the patch not listed in the body keep their previous order
    (but sort after the explicit ones because their indices are smaller
    than the new ones — callers should always send the full list).
    """
    patch = patch_svc.get_patch(patch_id)
    if not patch:
        return jsonify({"ok": False, "error": "patch_not_found"}), 404
    body = request.get_json(silent=True) or {}
    order = body.get("order") or []
    if not isinstance(order, list):
        return jsonify({"ok": False, "error": "order_must_be_list"}), 400
    from ..db import get_conn
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = get_conn()
    for i, tid in enumerate(order):
        if not isinstance(tid, str) or not tid.strip():
            continue
        conn.execute(
            "UPDATE tasks SET patch_order=?, updated_at=? "
            "WHERE task_id=? AND patch_id=?",
            (i, now, tid.strip().upper(), patch_id),
        )
    return jsonify({"ok": True, "patch_id": patch_id, "applied": len(order)})


@bp.route("/api/patches/<patch_id>/notes", methods=["POST", "PATCH"])
def api_patch_notes(patch_id: str):
    """Edit the free-form notes on a patch (title + notes)."""
    patch = patch_svc.get_patch(patch_id)
    if not patch:
        return jsonify({"ok": False, "error": "not_found"}), 404
    body = request.get_json(silent=True) or {}
    fields: list[str] = []
    args: list = []
    if "title" in body:
        fields.append("title=?")
        args.append(body["title"] or "")
    if "notes" in body:
        fields.append("notes=?")
        args.append(body["notes"] or "")
    if not fields:
        return jsonify({"ok": False, "error": "nothing_to_update"}), 400
    args.append(patch_id)
    from ..db import get_conn
    get_conn().execute(
        f"UPDATE patches SET {', '.join(fields)} WHERE patch_id=?", args,
    )
    return jsonify({"ok": True, "patch": patch_svc.get_patch(patch_id)})
