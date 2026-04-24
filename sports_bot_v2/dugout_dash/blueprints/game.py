"""GAME page blueprint — landing + per-game detail."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from flask import Blueprint, render_template

from core import espn_cache
from dugout_dash import config as cfg
from dugout_dash.positions import fetch_open_positions

bp = Blueprint("game", __name__)


@bp.route("/")
def index():
    games = espn_cache.get_scoreboard().get("games", [])
    open_ps = fetch_open_positions()
    selected = _pick_default(games, open_ps)
    pos = _match_position(selected, open_ps)
    return render_template(
        "game.html",
        ACTIVE="game",
        GAMES=games,
        SELECTED=selected["espn_id"] if selected else None,
        SELECTED_GAME=selected,
        POSITION=pos,
        TAZZ_URL=_tazz_url(selected),
        TAZZ_FORCE_LINK=cfg.TAZZ_FORCE_LINK,
        SHADOW_REC=_shadow_rec(pos),
        TRADE_HISTORY=_game_trade_history(selected),
        ORDERBOOK=_orderbook(pos),
        LIVE_COUNT=len(games),
        OPEN_COUNT=len(open_ps),
    )


@bp.route("/game/<espn_id>")
def detail(espn_id: str):
    games = espn_cache.get_scoreboard().get("games", [])
    selected = next((g for g in games if g["espn_id"] == espn_id), None)
    open_ps = fetch_open_positions()
    pos = _match_position(selected, open_ps)
    return render_template(
        "game.html",
        ACTIVE="game",
        GAMES=games,
        SELECTED=espn_id,
        SELECTED_GAME=selected,
        POSITION=pos,
        TAZZ_URL=_tazz_url(selected),
        TAZZ_FORCE_LINK=cfg.TAZZ_FORCE_LINK,
        SHADOW_REC=_shadow_rec(pos),
        TRADE_HISTORY=_game_trade_history(selected),
        ORDERBOOK=_orderbook(pos),
        LIVE_COUNT=len(games),
        OPEN_COUNT=len(open_ps),
    )


def _pick_default(games, positions):
    if positions and games:
        for p in positions:
            for g in games:
                if (g.get("home_abbr") or "").lower() in (p["market_slug"] or "").lower() \
                   or (g.get("away_abbr") or "").lower() in (p["market_slug"] or "").lower():
                    return g
    live = [g for g in games if g.get("inning", 0) > 0 and g.get("status") != "STATUS_FINAL"]
    return live[0] if live else (games[0] if games else None)


def _match_position(game, positions):
    if not game or not positions:
        return None
    for p in positions:
        slug = (p["market_slug"] or "").lower()
        if (game.get("home_abbr") or "").lower() in slug or (game.get("away_abbr") or "").lower() in slug:
            return p
    return None


def _tazz_url(game):
    if not game:
        return None
    side = cfg.TAZZ_TEAM_SIDE if cfg.TAZZ_TEAM_SIDE in ("home", "away") else "home"
    team_name = game.get(side) or ""
    slug = team_name.strip().lower().replace(" ", "_")
    if not slug:
        return None
    return cfg.TAZZ_BASE_URL.format(slug=slug)


def _game_trade_history(game):
    if not game:
        return []
    away = (game.get("away_abbr") or "").lower()
    home = (game.get("home_abbr") or "").lower()
    try:
        with sqlite3.connect(cfg.DB_PATH, timeout=2.0) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT ts_close, market_slug, side, entry_px, exit_px, pnl_usd, reason_close"
                " FROM trades WHERE status='closed'"
                " AND ts_close >= datetime('now','-1 day')"
                " ORDER BY ts_close DESC"
            ).fetchall()
    except sqlite3.Error:
        return []
    out = []
    for r in rows:
        slug = (r["market_slug"] or "").lower()
        if (away and away in slug) or (home and home in slug):
            out.append(dict(r))
    return out[:20]


def _shadow_rec(position):
    if not position:
        return None
    p = Path(cfg.SHADOW_LOG_PATH)
    if not p.exists():
        return None
    try:
        with p.open("r", encoding="utf-8") as f:
            f.seek(0, 2); size = f.tell(); f.seek(max(0, size - 4096))
            lines = f.read().splitlines()
    except Exception:
        return None
    for line in reversed(lines):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("market_slug") == position["market_slug"]:
            side = rec.get("recommended_side") or rec.get("side")
            prob = rec.get("model_prob") or rec.get("p")
            if side and prob is not None:
                return f"{side} {float(prob):.2f}"
    return None


def _orderbook(position):
    if not position:
        return None
    try:
        from core.state_hub import GLOBAL_STATE_HUB
        snap = GLOBAL_STATE_HUB.snapshot()
    except Exception:
        return None
    row = snap.get(position["market_slug"])
    if not row:
        return None
    return {
        "best_bid": row.get("best_bid"),
        "best_ask": row.get("best_ask"),
        "mark": row.get("current_price"),
        "spread": row.get("spread"),
    }
