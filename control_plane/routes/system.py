"""Runtime / system panel.

Shows the state of the Claude CLI integration (resolved path, version,
and candidate search list) and lets the operator override the path when
auto-discovery picks the wrong one.
"""
from __future__ import annotations

import json
import platform
import shutil
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request

from ..config import SETTINGS
from ..runner.bin_resolver import (
    ENV_VAR,
    get_override,
    probe,
    resolve_current,
    set_override,
)


bp = Blueprint("system", __name__)


def _load_state_json() -> dict | None:
    candidate = SETTINGS.repo_root / "sports_bot_v2" / "runtime" / "state.json"
    if not candidate.exists():
        return None
    try:
        return json.loads(candidate.read_text(encoding="utf-8"))
    except Exception:
        return None


def _claude_info() -> dict:
    resolved = resolve_current()
    info = {
        "platform": platform.system(),
        "env_var_name": ENV_VAR,
        "env_var_value": __import__("os").environ.get(ENV_VAR) or "",
        "override_path": get_override() or "",
        "resolved_path": resolved.path or "",
        "source": resolved.source,
        "candidates_tried": resolved.candidates_tried,
        "version": None,
        "ok": False,
        "error": resolved.error or "",
        "which_claude": shutil.which("claude") or "",
    }
    if resolved.path:
        probed = probe(resolved.path)
        info["version"] = probed.version or ""
        info["ok"] = probed.ok
        if probed.error and not info["error"]:
            info["error"] = probed.error
    return info


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
        claude_info=_claude_info(),
    )


@bp.route("/api/system/state", methods=["GET"])
def api_state():
    return jsonify(_load_state_json() or {})


@bp.route("/api/system/info", methods=["GET"])
def api_info():
    return jsonify({"ok": True, "claude": _claude_info()})


@bp.route("/api/system/claude-bin", methods=["GET"])
def api_claude_bin_get():
    return jsonify({"ok": True, "claude": _claude_info()})


@bp.route("/api/system/claude-bin", methods=["POST"])
def api_claude_bin_set():
    body = request.get_json(silent=True) or {}
    raw = (body.get("path") or "").strip()
    # Empty path clears the override and falls back to auto-discovery.
    if raw:
        if not Path(raw).is_file():
            return jsonify({"ok": False, "error": "path_not_found",
                            "detail": f"{raw} is not a file on this machine."}), 400
        probed = probe(raw)
        if not probed.ok:
            return jsonify({"ok": False, "error": "probe_failed",
                            "detail": probed.error or "<bin> --version did not succeed",
                            "version": probed.version}), 400
        set_override(raw)
    else:
        set_override(None)
    return jsonify({"ok": True, "claude": _claude_info()})


@bp.route("/api/system/claude-bin/test", methods=["POST"])
def api_claude_bin_test():
    body = request.get_json(silent=True) or {}
    path = (body.get("path") or "").strip() or (get_override() or resolve_current().path or "")
    if not path:
        return jsonify({"ok": False, "error": "no_path", "detail": "no path to test"}), 400
    probed = probe(path)
    return jsonify({
        "ok": probed.ok,
        "path": path,
        "version": probed.version,
        "error": probed.error,
    })
