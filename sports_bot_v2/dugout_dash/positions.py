"""Reads open positions + computes live P&L for templates."""
from __future__ import annotations

import sqlite3
from typing import Any

from dugout_dash import config as cfg


def fetch_open_positions() -> list[dict[str, Any]]:
    """Return a list of open trade dicts, each enriched with a live mark."""
    try:
        with sqlite3.connect(cfg.DB_PATH, timeout=2.0) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, ts_open, market_slug, market_id, side, qty, entry_px, fees_usd,"
                " confidence, mode, sport FROM trades WHERE status='open' ORDER BY ts_open DESC"
            ).fetchall()
    except sqlite3.Error:
        return []
    try:
        from core.state_hub import GLOBAL_STATE_HUB
        snap = GLOBAL_STATE_HUB.snapshot()
    except Exception:
        snap = {}
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        mark_row = snap.get(d["market_slug"]) or {}
        mark = mark_row.get("current_price")
        entry = float(d["entry_px"] or 0.0)
        qty = float(d["qty"] or 0.0)
        pnl = ((mark - entry) * qty) if mark is not None else None
        d["mark"] = mark
        d["pnl_usd"] = pnl
        d["pnl_pct"] = (pnl / (entry * qty) * 100.0) if (pnl is not None and entry > 0 and qty > 0) else None
        out.append(d)
    return out


def fetch_closed_today() -> list[dict[str, Any]]:
    """Closed trades in the last 24 h."""
    try:
        with sqlite3.connect(cfg.DB_PATH, timeout=2.0) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, ts_open, ts_close, market_slug, side, qty, entry_px, exit_px,"
                " pnl_usd, reason_close FROM trades"
                " WHERE status='closed' AND ts_close >= datetime('now', '-1 day')"
                " ORDER BY ts_close DESC"
            ).fetchall()
    except sqlite3.Error:
        return []
    return [dict(r) for r in rows]
