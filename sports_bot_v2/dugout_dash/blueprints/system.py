"""SYSTEM page — bot heartbeat, guardrails, controls."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from flask import Blueprint, render_template

from dugout_dash import config as cfg
from dugout_dash.events import GLOBAL_EVENT_BUS

bp = Blueprint("system", __name__)


def _read_state():
    p = Path(cfg.STATE_PATH)
    if not p.exists():
        return {"exists": False}
    try:
        return {"exists": True, "mtime": p.stat().st_mtime, "data": json.loads(p.read_text(encoding="utf-8"))}
    except Exception as e:
        return {"exists": True, "error": str(e)}


def _today_pnl():
    try:
        with sqlite3.connect(cfg.DB_PATH, timeout=2.0) as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(pnl_usd),0), COUNT(*), "
                " SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END)"
                " FROM trades WHERE status='closed'"
                " AND ts_close >= datetime('now','-1 day')"
            ).fetchone()
            pnl, total, wins = (row[0] or 0.0), (row[1] or 0), (row[2] or 0)
            win_rate = (wins / total * 100.0) if total else None
            return {"pnl": pnl, "trades": total, "win_rate_pct": win_rate}
    except Exception as e:
        return {"error": str(e), "pnl": 0.0, "trades": 0, "win_rate_pct": None}


@bp.route("/system")
def index():
    st = _read_state()
    stale = True
    if st.get("exists") and "mtime" in st:
        stale = (time.time() - st["mtime"]) > 90.0
    return render_template(
        "system.html",
        ACTIVE="system",
        STATE=st,
        STALE=stale,
        TODAY=_today_pnl(),
        SSE_CLIENT_COUNT=GLOBAL_EVENT_BUS.subscriber_count(),
    )


@bp.route("/api/control/<action>", methods=["POST"])
def control(action: str):
    if action not in {"pause", "resume", "flat_all"}:
        return {"error": "unknown action"}, 400
    path = Path(cfg.STATE_PATH)
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        data = {}
    if action == "pause":
        data["bot_paused"] = True
    elif action == "resume":
        data["bot_paused"] = False
    elif action == "flat_all":
        data["flat_all_request_ts"] = time.time()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return {"ok": True, "action": action}
    except Exception as e:
        return {"error": str(e)}, 500
