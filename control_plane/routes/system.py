"""Runtime / system panel (Phase 1 stub — reads state.json if present)."""
from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, jsonify, render_template

from ..config import SETTINGS


bp = Blueprint("system", __name__)


def _load_state_json() -> dict | None:
    # sports_bot_v2/runtime/state.json is the most authoritative runtime blob.
    candidate = SETTINGS.repo_root / "sports_bot_v2" / "runtime" / "state.json"
    if not candidate.exists():
        return None
    try:
        return json.loads(candidate.read_text(encoding="utf-8"))
    except Exception:
        return None


@bp.route("/system", methods=["GET"])
def system_page():
    state = _load_state_json()
    launcher_pid = None
    pid_file = SETTINGS.repo_root / "sports_bot_v2" / "runtime" / "launcher.pid"
    if pid_file.exists():
        try:
            launcher_pid = int(pid_file.read_text().strip())
        except Exception:
            launcher_pid = None
    return render_template(
        "system.html",
        state=state,
        launcher_pid=launcher_pid,
    )


@bp.route("/api/system/state", methods=["GET"])
def api_state():
    return jsonify(_load_state_json() or {})
