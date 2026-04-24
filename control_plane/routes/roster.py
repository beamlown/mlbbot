"""Roster management — Front Office, Graveyard, release/sign endpoints.

Reads use stats.persona_stats(); writes go through permissions.require()
with action='release_persona' or 'sign_persona'. All four /api/roster/*
endpoints return JSON {ok: bool, ...} matching the rest of the app.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, render_template, request

from ..db import get_conn
from ..permissions import can, PermissionDenied
from ..stats import persona_stats
from ..roster_names import generate_name


bp = Blueprint("roster", __name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _acting_role() -> str:
    row = get_conn().execute(
        "SELECT value FROM settings WHERE key='acting_role'"
    ).fetchone()
    return (row["value"] if row else "operator").strip().lower()


def _has_active_run_for_role(role: str) -> bool:
    row = get_conn().execute(
        "SELECT 1 FROM runs WHERE role=? AND status IN ('queued','running') LIMIT 1",
        (role,),
    ).fetchone()
    return row is not None


@bp.get("/roster")
def front_office():
    """Active personas + open tryout slots per role."""
    conn = get_conn()
    active = [dict(r) for r in conn.execute(
        "SELECT * FROM agent_profiles "
        "WHERE status='ACTIVE' AND enabled=1 "
        "ORDER BY jersey_number"
    ).fetchall()]
    stats = {p["profile_id"]: persona_stats(p["profile_id"]) for p in active}

    # Vacant slots: roles in the seeded set that have no ACTIVE persona.
    SEEDED_ROLES = (
        "HAIKU_WORKER", "SONNET_MANAGER", "SONNET_TRIAGE",
        "OPUS_AUDITOR", "OPUS_PATCH_REVIEWER",
    )
    occupied = {p["role"] for p in active}
    vacant = [r for r in SEEDED_ROLES if r not in occupied]

    return render_template(
        "roster.html",
        active=active, stats=stats, vacant=vacant,
    )


@bp.get("/roster/graveyard")
def graveyard():
    """Wall of retired personas, sorted by career AVG (numeric)."""
    conn = get_conn()
    released = [dict(r) for r in conn.execute(
        "SELECT * FROM agent_profiles WHERE status='RELEASED' "
        "ORDER BY released_at DESC"
    ).fetchall()]
    stats = {p["profile_id"]: persona_stats(p["profile_id"]) for p in released}

    def _avg_num(s):
        a = s["AVG"]
        if a == "—":
            return -1.0
        return float("0" + a)

    released.sort(
        key=lambda p: (_avg_num(stats[p["profile_id"]]), stats[p["profile_id"]]["HR"]),
        reverse=True,
    )
    return render_template("graveyard.html", released=released, stats=stats)


@bp.post("/api/roster/<profile_id>/release")
def release_persona(profile_id: str):
    if not can(_acting_role(), "release_persona"):
        return jsonify({"ok": False, "error": "permission denied"}), 403
    body = request.get_json(silent=True) or {}
    reason = (body.get("reason") or "").strip() or "no reason given"

    conn = get_conn()
    prof = conn.execute(
        "SELECT role FROM agent_profiles WHERE profile_id=?", (profile_id,)
    ).fetchone()
    if not prof:
        return jsonify({"ok": False, "error": "no such persona"}), 404
    if _has_active_run_for_role(prof["role"]):
        return jsonify({"ok": False,
                        "error": "active run in flight — wait for it to finish"}), 409
    conn.execute(
        "UPDATE agent_profiles SET status='RELEASED', released_at=?, "
        "released_reason=? WHERE profile_id=?",
        (_now_iso(), reason, profile_id),
    )
    return jsonify({"ok": True, "profile_id": profile_id})


@bp.post("/api/roster/<role>/sign")
def sign_persona(role: str):
    if not can(_acting_role(), "sign_persona"):
        return jsonify({"ok": False, "error": "permission denied"}), 403
    role = role.upper().strip()
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip() or generate_name()

    conn = get_conn()
    # Inherit adapter/model/color/icon/allowed_states from any prior persona of this role
    # (active or released) so we don't have to hard-code role configs here.
    prior = conn.execute(
        "SELECT adapter, model, color, icon, allowed_states, prompt_extra "
        "FROM agent_profiles WHERE role=? ORDER BY created_at LIMIT 1",
        (role,),
    ).fetchone()
    if not prior:
        return jsonify({"ok": False,
                        "error": f"role={role} has no template to inherit from"}), 400

    used = {r["jersey_number"] for r in conn.execute(
        "SELECT jersey_number FROM agent_profiles WHERE jersey_number IS NOT NULL"
    ).fetchall()}
    jersey = next((n for n in range(2, 100) if n not in used), None)
    if jersey is None:
        return jsonify({"ok": False, "error": "all jersey numbers in use"}), 409

    new_id = f"{role.lower()}_{uuid.uuid4().hex[:8]}"
    now = _now_iso()
    conn.execute(
        """INSERT INTO agent_profiles
           (profile_id, display, role, adapter, model, color, icon, tagline,
            prompt_extra, allowed_states, enabled, status, signed_at,
            jersey_number, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,1,'ACTIVE',?,?,?,?)""",
        (new_id, name, role, prior["adapter"], prior["model"], prior["color"],
         prior["icon"], None, prior["prompt_extra"], prior["allowed_states"],
         now, jersey, now, now),
    )
    return jsonify({"ok": True, "profile_id": new_id, "name": name,
                    "jersey_number": jersey})


@bp.get("/api/roster/stats/<profile_id>")
def roster_stats(profile_id: str):
    return jsonify({"ok": True, "stats": persona_stats(profile_id)})
