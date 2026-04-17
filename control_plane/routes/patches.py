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
