"""
dashboard_server.py — Live dashboard HTTP server for sports_bot_v2 (MLB)
Port: 8900 (set via DASHBOARD_PORT env var)
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
import threading
import time
import urllib.request
import webbrowser
from contextlib import contextmanager
from datetime import date as _date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from core.market_stream import GLOBAL_MARKET_STREAM
from core.state_hub import GLOBAL_STATE_HUB
from core.discovery import discover_markets
from sports.mlb.adapter import KEYWORDS as MLB_KEYWORDS, SPORT as MLB_SPORT, TAG_SLUG as MLB_TAG_SLUG, TOURNAMENT as MLB_TOURNAMENT

try:
    from core.model_bridge import ENABLE_MODEL_BRIDGE as _BRIDGE_ENABLED
except Exception:
    _BRIDGE_ENABLED = False

# Load .env
def _load_env(path=".env"):
    try:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip(); v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except FileNotFoundError:
        pass

_load_env()

# ── Config ────────────────────────────────────────────────────────────────────
SPORT        = os.getenv("SPORT", "baseball")
PORT         = int(os.getenv("DASHBOARD_PORT", "8900"))
STARTING_BANKROLL = float(os.getenv("STARTING_BANKROLL", "500"))
DB_PATH      = os.getenv("DB_PATH", "trades_sports.db")
STATE_PATH   = os.getenv("STATE_PATH", "runtime/state.json")
DISCOVERY_PATH = os.getenv("DISCOVERY_CACHE_PATH", "runtime/last_discovery.json")
BOT_STALE_SEC = 90   # MLB loops are slower, use generous stale threshold
AUTO_TAKE_PROFIT_PCT = float(os.getenv("AUTO_TAKE_PROFIT_PCT", "0.85"))
AUTO_STOP_LOSS_PCT   = float(os.getenv("AUTO_STOP_LOSS_PCT", "0.20"))
CLOB_BOOK = "https://clob.polymarket.com/book"
STALE_REST_POLL_SEC = 30.0     # Only trigger REST poll if mark is older than this
STALE_REST_THROTTLE_SEC = 20.0 # Min seconds between REST polls for same slug
_rest_poll_ts: dict[str, float] = {}  # slug -> last REST poll wall-clock time
_rest_poll_lock = threading.Lock()

# mlb_model shadow log — read-only, no execution dependency.
# Set MLB_SHADOW_LOG_PATH in .env to point at mlb_model's log file.
MLB_SHADOW_LOG_PATH = os.getenv(
    "MLB_SHADOW_LOG_PATH",
    os.path.join(os.path.dirname(__file__), "..", "mlb_model", "logs", "shadow_recommendations.jsonl"),
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [DASH] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("dashboard")

# ── ESPN MLB scoreboard cache ─────────────────────────────────────────────────
_espn_lock = threading.Lock()
_espn_scoreboard: dict = {"games": [], "fetched_at": "", "error": None}
_espn_detail: dict[str, dict] = {}

ESPN_SB_URL = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"
ESPN_DETAIL_URL = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/summary?event={}"
MLB_STATS_API = "https://statsapi.mlb.com/api/v1"


def _http_get(url: str, timeout: int = 8) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "march-madness-bot/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _build_games_from_raw(raw: dict) -> list[dict]:
    games = []
    for event in raw.get("events", []):
        espn_id = str(event.get("id", ""))
        comp = event.get("competitions", [{}])[0]
        competitors = comp.get("competitors", [])
        home = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away = next((c for c in competitors if c.get("homeAway") == "away"), {})
        status_obj = comp.get("status", {})
        status_type = status_obj.get("type", {})
        status_name = status_type.get("name", "STATUS_UNKNOWN")
        inning = int(status_obj.get("period") or 0)

        # Situation from scoreboard
        sb_sit = comp.get("situation") or {}

        game: dict = {
            "espn_id": espn_id,
            "home": (home.get("team") or {}).get("displayName", "?"),
            "away": (away.get("team") or {}).get("displayName", "?"),
            "home_score": int(home.get("score", 0) or 0),
            "away_score": int(away.get("score", 0) or 0),
            "inning": inning,
            "inning_half": "bottom" if sb_sit.get("isTopInning") is False else "top",
            "status": status_name,
            "status_display": status_type.get("shortDetail", ""),
            "outs": int(sb_sit.get("outs") or 0),
            "balls": int(sb_sit.get("balls") or 0),
            "strikes": int(sb_sit.get("strikes") or 0),
            "on_first": bool(sb_sit.get("onFirst")),
            "on_second": bool(sb_sit.get("onSecond")),
            "on_third": bool(sb_sit.get("onThird")),
            "current_batter": (sb_sit.get("batter") or {}).get("displayName", ""),
            "current_pitcher": (sb_sit.get("pitcher") or {}).get("displayName", ""),
            "home_pitcher": "",
            "away_pitcher": "",
            "home_hits": int(home.get("hits") or 0),
            "away_hits": int(away.get("hits") or 0),
            "home_errors": int(home.get("errors") or 0),
            "away_errors": int(away.get("errors") or 0),
            "last_play": (sb_sit.get("lastPlay") or {}).get("text", "") if isinstance(sb_sit.get("lastPlay"), dict) else "",
        }

        # Merge detail if cached
        with _espn_lock:
            detail = _espn_detail.get(espn_id) or {}
        if detail:
            _enrich_from_detail(game, detail)

        games.append(game)
    return games


def _enrich_from_detail(game: dict, detail: dict) -> None:
    """Pull pitcher names and last play from full summary."""
    try:
        boxscore = detail.get("boxscore") or {}
        teams = boxscore.get("teams") or {}
        for side in ["home", "away"]:
            team_data = teams.get(side) or {}
            pitchers = team_data.get("pitchers") or []
            if pitchers:
                pid = str(pitchers[-1])
                players = team_data.get("players") or {}
                person = (players.get(f"ID{pid}") or {}).get("person") or {}
                name = person.get("fullName") or person.get("name") or ""
                game[f"{side}_pitcher"] = name
    except Exception:
        pass

    try:
        plays = detail.get("plays") or []
        if plays:
            game["last_play"] = str(plays[-1].get("text") or "")
    except Exception:
        pass


def _bg_espn_refresh():
    """Background thread: refresh MLB scoreboard every 15s, detail every 30s."""
    detail_last: dict[str, float] = {}
    while True:
        try:
            raw = _http_get(ESPN_SB_URL, timeout=10)
            games = _build_games_from_raw(raw)
            result = {"games": games, "fetched_at": datetime.now(timezone.utc).isoformat(), "error": None}
            with _espn_lock:
                _espn_scoreboard.update(result)

            # Refresh detail for live games
            now = time.time()
            for g in games:
                eid = g.get("espn_id", "")
                if not eid:
                    continue
                status_n = (g.get("status") or "").lower()
                if "final" in status_n or "scheduled" in status_n or "pre" in status_n or "warmup" in status_n:
                    continue
                if now - detail_last.get(eid, 0) >= 30:
                    try:
                        detail_raw = _http_get(ESPN_DETAIL_URL.format(eid), timeout=8)
                        with _espn_lock:
                            _espn_detail[eid] = detail_raw
                        detail_last[eid] = now
                    except Exception as exc:
                        log.debug("Detail fetch %s failed: %s", eid, exc)
                    time.sleep(0.5)

        except Exception as exc:
            log.warning("ESPN MLB refresh failed: %s", exc)
            with _espn_lock:
                _espn_scoreboard["error"] = str(exc)

        time.sleep(15)


# ── DB helpers ────────────────────────────────────────────────────────────────
@contextmanager
def _db():
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
    finally:
        conn.close()


def _init_manual_trades_table():
    try:
        with _db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS manual_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_open TEXT NOT NULL, ts_close TEXT,
                    market_slug TEXT, question TEXT, side TEXT,
                    entry_px REAL, exit_px REAL, qty_usd REAL DEFAULT 50.0,
                    pnl_usd REAL, status TEXT DEFAULT 'open', note TEXT
                )
            """)
            conn.commit()
    except Exception:
        pass


def _daily_pnl_history() -> list[dict]:
    try:
        with _db() as conn:
            rows = conn.execute(
                "SELECT DATE(ts_close) as day, SUM(pnl_usd) as pnl "
                "FROM trades WHERE status='closed' AND ts_close IS NOT NULL "
                "GROUP BY day ORDER BY day ASC LIMIT 30"
            ).fetchall()
        return [{"day": r["day"], "pnl": round(float(r["pnl"] or 0), 4)} for r in rows]
    except Exception:
        return []


def _fetch_trades(limit: int = 50) -> list[dict]:
    try:
        with _db() as conn:
            rows = conn.execute(
                "SELECT id,ts_open,ts_close,market_slug,side,entry_px,exit_px,"
                "pnl_usd,reason_open,reason_close,confidence,mode,status,qty,source "
                "FROM trades ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            result = []
            for r in rows:
                entry_px = float(r["entry_px"] or 0.0)
                side = r["side"] or ""
                if side == "BUY_NO":
                    tp_price = max(0.01, 1.0 - entry_px * (1 + AUTO_TAKE_PROFIT_PCT))
                    sl_price = min(0.99, entry_px * (1 + AUTO_STOP_LOSS_PCT))
                else:
                    tp_price = min(0.99, entry_px * (1 + AUTO_TAKE_PROFIT_PCT))
                    sl_price = max(0.01, entry_px * (1 - AUTO_STOP_LOSS_PCT))
                result.append({
                    "id": r["id"], "ts_open": r["ts_open"], "ts_close": r["ts_close"],
                    "market_slug": r["market_slug"], "side": side,
                    "entry_px": r["entry_px"], "exit_px": r["exit_px"],
                    "pnl_usd": r["pnl_usd"], "reason_open": r["reason_open"],
                    "reason_close": r["reason_close"], "confidence": r["confidence"],
                    "mode": r["mode"], "status": r["status"], "qty": r["qty"],
                    "source": r["source"] or "bot",
                    "tp_price": tp_price,
                    "sl_price": sl_price,
                })
            # Manual trades
            try:
                mrows = conn.execute(
                    "SELECT id,ts_open,ts_close,market_slug,question,side,entry_px,"
                    "exit_px,qty_usd,pnl_usd,status,note FROM manual_trades ORDER BY id DESC LIMIT ?",
                    (limit,)
                ).fetchall()
                for r in mrows:
                    result.append({
                        "id": f"M{r['id']}", "ts_open": r["ts_open"], "ts_close": r["ts_close"],
                        "market_slug": r["market_slug"] or r["question"] or "manual",
                        "side": r["side"], "entry_px": r["entry_px"], "exit_px": r["exit_px"],
                        "pnl_usd": r["pnl_usd"], "reason_open": r["note"],
                        "reason_close": None, "confidence": None,
                        "mode": "manual", "status": r["status"], "qty": r["qty_usd"],
                        "source": "manual",
                    })
            except Exception:
                pass
            result.sort(key=lambda x: str(x.get("ts_open") or ""), reverse=True)
            return result[:limit]
    except Exception as exc:
        log.error("fetch_trades error: %s", exc)
        return []


def _compute_open_trade_accounting() -> dict:
    try:
        with _db() as conn:
            rows = conn.execute(
                "SELECT side, entry_px, qty, source FROM trades WHERE status='open' ORDER BY id ASC"
            ).fetchall()
        committed = 0.0
        for r in rows:
            entry_px = float(r["entry_px"] or 0.0)
            qty = float(r["qty"] or 0.0)
            committed += entry_px * qty
        raw_cash = STARTING_BANKROLL - committed
        if raw_cash < 0:
            log.warning("available_cash would be negative (committed=%.2f > bankroll=%.2f) — clamping to 0", committed, STARTING_BANKROLL)
        return {
            "open_count": len(rows),
            "capital_committed": round(committed, 2),
            "available_cash": round(max(0.0, raw_cash), 2),
        }
    except Exception:
        return {
            "open_count": 0,
            "capital_committed": 0.0,
            "available_cash": round(STARTING_BANKROLL, 2),
        }


def _refresh_discovery_cache_if_needed() -> None:
    try:
        discover_markets(MLB_TAG_SLUG, MLB_KEYWORDS, MLB_SPORT, MLB_TOURNAMENT)
    except Exception:
        pass


def _tracked_open_assets() -> dict[str, dict[str, str]]:
    tracked: dict[str, dict[str, str]] = {}
    trades = _fetch_trades(limit=100)
    p = Path(DISCOVERY_PATH)
    if not p.exists():
        return tracked
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        markets = data if isinstance(data, list) else data.get("markets", [])
        market_by_slug = {str(m.get("slug") or ""): m for m in markets if m.get("slug")}
        market_by_id = {str(m.get("market_id") or m.get("id") or ""): m for m in markets if (m.get("market_id") or m.get("id"))}
    except Exception:
        return tracked
    for t in trades:
        if t.get("status") != "open":
            continue
        slug = str(t.get("market_slug") or "")
        market_id = str(t.get("market_id") or "")
        side = str(t.get("side") or "")
        m = market_by_slug.get(slug) or market_by_id.get(market_id) or {}
        yes_token_id = str(m.get("yes_token_id") or "")
        no_token_id = str(m.get("no_token_id") or "")
        asset_id = yes_token_id if side == "BUY_YES" else no_token_id
        if not slug or not asset_id:
            continue
        tracked[slug] = {
            "market_slug": slug,
            "market_id": str(m.get("market_id") or market_id or ""),
            "asset_id": asset_id,
        }
    return tracked


def _refresh_game_state_hub() -> None:
    try:
        games = _read_games().get("games") or []
    except Exception:
        games = []
    by_slug = {str(g.get("slug") or ""): g for g in games if g.get("slug")}
    trades = _fetch_trades(limit=100)
    for t in trades:
        if t.get("status") != "open":
            continue
        slug = str(t.get("market_slug") or "")
        g = by_slug.get(slug) or {}
        GLOBAL_STATE_HUB.update_game(
            market_slug=slug,
            game_status=g.get("game_status"),
            inning=g.get("inning"),
            inning_half=g.get("inning_half"),
            outs=g.get("outs"),
            home_score=g.get("home_score"),
            away_score=g.get("away_score"),
            game_source="games_poll",
        )


def _poll_stale_mark(slug: str, market_id: str, asset_id: str) -> None:
    """Fetch current price from Polymarket CLOB REST API and inject into state_hub."""
    try:
        url = f"{CLOB_BOOK}?token_id={asset_id}"
        data = _http_get(url, timeout=5)
        bids = data.get("bids") or []
        asks = data.get("asks") or []
        best_bid = float(bids[0]["price"]) if bids else None
        best_ask = float(asks[0]["price"]) if asks else None
        current_price = best_bid if best_bid is not None else best_ask
        spread = round(best_ask - best_bid, 6) if (best_bid is not None and best_ask is not None) else None
        if current_price is not None:
            GLOBAL_STATE_HUB.update_mark(
                market_slug=slug,
                market_id=market_id,
                asset_id=asset_id,
                current_price=current_price,
                best_bid=best_bid,
                best_ask=best_ask,
                spread=spread,
                source="rest_fallback",
            )
            log.info("[STALE_POLL] %s → cp=%.4f bid=%s ask=%s", slug, current_price, best_bid, best_ask)
        else:
            log.warning("[STALE_POLL] %s → empty book (no bid or ask)", slug)
    except Exception as exc:
        log.warning("[STALE_POLL] %s failed: %s", slug, exc)


def _stream_positions_mark() -> dict:
    tracked = _tracked_open_assets()
    open_trades = [t for t in _fetch_trades(limit=100) if t.get("status") == "open"]
    if open_trades and not tracked:
        _refresh_discovery_cache_if_needed()
        tracked = _tracked_open_assets()
    GLOBAL_MARKET_STREAM.update_tracked_assets(tracked)
    GLOBAL_MARKET_STREAM.start()
    _refresh_game_state_hub()
    marks = GLOBAL_STATE_HUB.snapshot(stale_after_sec=15.0)
    # REST fallback: for any mark stale >30s that hasn't been polled in the last 20s,
    # fetch current price from Polymarket CLOB REST and inject into state_hub.
    _now_ts = time.time()
    _to_poll = []
    with _rest_poll_lock:
        for _slug, _info in tracked.items():
            _mark = marks.get(_slug) or {}
            _mark_age = _now_ts - float(_mark.get("source_ts") or 0)
            _last_poll = _rest_poll_ts.get(_slug, 0)
            if _mark_age > STALE_REST_POLL_SEC and (_now_ts - _last_poll) > STALE_REST_THROTTLE_SEC:
                _rest_poll_ts[_slug] = _now_ts
                _to_poll.append((_slug, _info["market_id"], _info["asset_id"]))
    for _slug, _market_id, _asset_id in _to_poll:
        _poll_stale_mark(_slug, _market_id, _asset_id)
    if _to_poll:
        marks = GLOBAL_STATE_HUB.snapshot(stale_after_sec=15.0)
    trades = _fetch_trades(limit=100)
    positions = []
    live_equity_total = 0.0
    stale_count = 0
    for t in trades:
        if t.get("status") != "open":
            continue
        slug = str(t.get("market_slug") or "")
        mark = marks.get(slug) or {}
        current_price = mark.get("current_price")
        entry_px = float(t.get("entry_px") or 0.0)
        qty = float(t.get("qty") or 0.0)
        side = str(t.get("side") or "")
        current_price_stale = bool(mark.get("stale", True)) or current_price is None
        if current_price_stale:
            stale_count += 1
        unrealized_pnl_usd = None
        live_equity_usd = None
        if current_price is not None and qty > 0:
            current_price = float(current_price)
            live_equity_usd = round(qty * current_price, 4)
            unrealized_pnl_usd = round((current_price - entry_px) * qty, 4)
            live_equity_total += live_equity_usd
        positions.append({
            "market_slug": slug,
            "current_price": current_price,
            "current_price_stale": current_price_stale,
            "unrealized_pnl_usd": unrealized_pnl_usd,
            "live_equity_usd": live_equity_usd,
            "best_bid": mark.get("best_bid"),
            "best_ask": mark.get("best_ask"),
            "spread": mark.get("spread"),
            "source_ts": datetime.fromtimestamp(mark.get("source_ts"), timezone.utc).isoformat() if mark.get("source_ts") else None,
            "mark_source": mark.get("source") or "poll_fallback",
            "game_status": mark.get("game_status"),
            "inning": mark.get("inning"),
            "inning_half": mark.get("inning_half"),
            "outs": mark.get("outs"),
            "home_score": mark.get("home_score"),
            "away_score": mark.get("away_score"),
            "game_source_ts": datetime.fromtimestamp(mark.get("game_source_ts"), timezone.utc).isoformat() if mark.get("game_source_ts") else None,
            "game_stale": mark.get("game_stale", True),
            "game_source": mark.get("game_source") or "games_poll",
        })
    return {
        "type": "positions_mark",
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": "dashboard_server",
        "stale": stale_count > 0,
        "open_count": len(positions),
        "live_equity_total": round(live_equity_total, 4),
        "positions": positions,
    }


def _read_state() -> dict:
    try:
        p = Path(STATE_PATH)
        if not p.exists():
            return {"error": "state.json not found — bot starting up?", "stale": True}
        age = time.time() - p.stat().st_mtime
        with open(p, encoding="utf-8") as f:
            state = json.load(f)
        net_pnl = float((state.get("pnl") or {}).get("realized", 0) or 0)
        current = STARTING_BANKROLL + net_pnl
        pct = (current - STARTING_BANKROLL) / STARTING_BANKROLL * 100 if STARTING_BANKROLL else 0
        acct = _compute_open_trade_accounting()
        session_start_ts = int((state.get("pnl") or {}).get("session_start_ts", 0) or 0)
        try:
            with _db() as conn:
                _row = conn.execute(
                    "SELECT COALESCE(SUM(pnl_usd), 0) FROM trades WHERE status='closed' AND ts_close >= ?",
                    (session_start_ts,)
                ).fetchone()
            session_pnl = round(float(_row[0] or 0), 4)
        except Exception:
            session_pnl = 0.0
        state["bankroll"] = {
            "start": STARTING_BANKROLL, "current": round(current, 2),
            "pct_gain": round(pct, 2), "net_pnl": round(net_pnl, 2),
            "capital_committed": acct["capital_committed"],
            "available_cash": round(max(0.0, current - acct["capital_committed"]), 2),
            "open_trade_count": acct["open_count"],
            "session_pnl": session_pnl,
            "session_start_ts": session_start_ts,
        }
        state["stale"] = age > BOT_STALE_SEC
        state["file_age_sec"] = round(age, 1)
        state["bridge_enabled"] = _BRIDGE_ENABLED

        try:
            with _db() as conn:
                r25_rows = conn.execute(
                    "SELECT pnl_usd FROM trades WHERE status='closed' AND pnl_usd IS NOT NULL "
                    "ORDER BY COALESCE(ts_close, ts_open) DESC, id DESC LIMIT 25"
                ).fetchall()
            pnls = [float(r["pnl_usd"] or 0.0) for r in r25_rows]
            sample_size = len(pnls)
            wins = sum(1 for p in pnls if p > 0)
            losses = sum(1 for p in pnls if p <= 0)
            win_rate = round((wins / sample_size), 4) if sample_size else None
            expectancy = round(sum(pnls) / sample_size, 4) if sample_size else None
            state["r25"] = {
                "win_rate": win_rate,
                "wins": wins,
                "losses": losses,
                "expectancy": expectancy,
                "sample_size": sample_size,
            }
        except Exception as exc:
            state["r25"] = {
                "win_rate": None,
                "wins": 0,
                "losses": 0,
                "expectancy": None,
                "sample_size": 0,
                "error": str(exc),
            }

        return state
    except Exception as exc:
        return {"error": str(exc), "stale": True}


def _read_markets() -> list[dict]:
    try:
        p = Path(DISCOVERY_PATH)
        if not p.exists():
            return []
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        markets = data if isinstance(data, list) else data.get("markets", [])
        return [
            {
                "slug": m.get("slug", ""), "question": m.get("question", ""),
                "yes_price": m.get("yes_price"), "no_price": m.get("no_price"),
                "end_date": m.get("end_iso") or m.get("end_date"),
            }
            for m in markets[:30]
        ]
    except Exception:
        return []


def _read_candidates() -> list[dict]:
    try:
        p = Path(f"logs/audit_candidates_{SPORT}.jsonl")
        if not p.exists():
            return []
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[-2000:]
        by_slug: dict[str, dict] = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                slug = r.get("slug", "")
                if slug:
                    by_slug[slug] = r
            except Exception:
                pass
        return sorted(by_slug.values(), key=lambda x: float(x.get("confidence") or 0), reverse=True)[:25]
    except Exception as exc:
        log.error("read_candidates error: %s", exc)
        return []


def _read_mlb_shadow(limit: int = 30) -> dict:
    """
    Read the mlb_model shadow log and return a dashboard-ready summary.
    Pure file read — no dependency on mlb_model code.
    """
    try:
        p = Path(MLB_SHADOW_LOG_PATH)
        if not p.exists():
            return {"error": f"shadow log not found: {MLB_SHADOW_LOG_PATH}", "recs": [], "pnl": {}}

        age_sec = round(time.time() - p.stat().st_mtime, 1)
        lines = p.read_text(encoding="utf-8").splitlines()

        default_shadow_size_usd = float(os.getenv("SHADOW_POSITION_SIZE_USD", "50"))
        tp_buffer = float(os.getenv("SHADOW_TP_BUFFER", "0.0"))
        sl_buffer = float(os.getenv("SHADOW_SL_BUFFER", "0.10"))

        recs_by_market: dict[str, dict] = {}
        outcomes: dict[str, bool] = {}
        actionable_count = 0
        no_trade_count = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("event_type") == "outcome":
                outcomes[obj["market_id"]] = obj["yes_resolved"]
            elif "action" in obj:
                if obj["action"] in ("BUY_YES", "BUY_NO"):
                    actionable_count += 1
                    recs_by_market[obj["market_id"]] = obj
                else:
                    no_trade_count += 1

        def _entry_price(rec: dict) -> float | None:
            price = rec.get("market_yes_cost" if rec.get("action") == "BUY_YES" else "market_no_cost")
            if price is None:
                price = rec.get("ask_yes" if rec.get("action") == "BUY_YES" else "ask_no")
            try:
                return float(price) if price is not None else None
            except (TypeError, ValueError):
                return None

        def _current_price(rec: dict) -> float | None:
            price = rec.get("ask_yes" if rec.get("action") == "BUY_YES" else "ask_no")
            try:
                return float(price) if price is not None else None
            except (TypeError, ValueError):
                return None

        def _tp_price(rec: dict) -> float | None:
            fair = rec.get("fair_win_prob")
            try:
                fair = float(fair)
            except (TypeError, ValueError):
                return None
            target = fair if rec.get("action") == "BUY_YES" else (1.0 - fair)
            return round(max(0.0, min(1.0, target + tp_buffer)), 4)

        def _sl_price(rec: dict, entry_price: float | None) -> float | None:
            if entry_price is None:
                return None
            return round(max(0.0, min(1.0, entry_price - sl_buffer)), 4)

        def _unrealized_pnl_dollars(action: str, entry_price: float | None,
                                    current_price: float | None, size_usd: float) -> float | None:
            if entry_price is None or current_price is None:
                return None
            if action == "BUY_YES":
                return round((current_price - entry_price) * size_usd, 4)
            if action == "BUY_NO":
                return round((entry_price - current_price) * size_usd, 4)
            return None

        def _status_label(rec: dict, current_price: float | None,
                          tp_price: float | None, sl_price: float | None,
                          resolved: bool, yes_resolved: bool | None) -> str:
            action = rec.get("action")
            if resolved:
                won = (action == "BUY_YES" and yes_resolved is True) or (
                    action == "BUY_NO" and yes_resolved is False
                )
                return "RESOLVED_WIN" if won else "RESOLVED_LOSS"
            if current_price is None:
                return "PENDING"
            if tp_price is not None and current_price >= tp_price:
                return "TP_ZONE"
            if sl_price is not None and current_price <= sl_price:
                return "SL_ZONE"
            return "OPEN"

        # Shadow P&L from resolved actionable recs
        wins = losses = matched = 0
        pnl = 0.0
        for mid, r in recs_by_market.items():
            if mid not in outcomes:
                continue
            matched += 1
            yes_won = outcomes[mid]
            action = r["action"]
            ask = _entry_price(r) or 0.5
            won = (action == "BUY_YES" and yes_won) or (action == "BUY_NO" and not yes_won)
            if won:
                wins += 1
                pnl += (1.0 / ask - 1.0)
            else:
                losses += 1
                pnl -= 1.0

        today_str = _date.today().isoformat()

        def _slug_is_today_or_newer(slug: str) -> bool:
            parts = slug.rsplit("-", 3)
            if len(parts) == 4:
                try:
                    slug_date = f"{parts[1]}-{parts[2]}-{parts[3]}"
                    return slug_date >= today_str
                except Exception:
                    return True
            return True

        recs_by_market = {
            mid: rec for mid, rec in recs_by_market.items()
            if _slug_is_today_or_newer(str(rec.get("market_slug", "")))
        }
        outcomes = {
            mid: yes_resolved for mid, yes_resolved in outcomes.items()
            if mid in recs_by_market
        }

        # Most recent actionable recs for display (newest first)
        recent = sorted(
            recs_by_market.values(),
            key=lambda x: x.get("ts", ""),
            reverse=True,
        )[:limit]

        display = []
        total_unrealized_dollars = 0.0
        open_count = 0
        for r in recent:
            mid = r["market_id"]
            resolved = mid in outcomes
            yes_resolved = outcomes.get(mid)
            entry_price = _entry_price(r)
            current_price = _current_price(r)
            tp_price = _tp_price(r)
            sl_price = _sl_price(r, entry_price)
            size_usd = default_shadow_size_usd
            unrealized_pnl_dollars = _unrealized_pnl_dollars(
                r["action"], entry_price, current_price, size_usd,
            )
            status = _status_label(r, current_price, tp_price, sl_price, resolved, yes_resolved)

            if not resolved:
                open_count += 1
                if unrealized_pnl_dollars is not None:
                    total_unrealized_dollars += unrealized_pnl_dollars

            display.append({
                "ts": r.get("ts", ""),
                "action": r["action"],
                "tracked_team": r.get("tracked_team", ""),
                "home_team": r.get("home_team", ""),
                "away_team": r.get("away_team", ""),
                "inning": r.get("inning", 0),
                "fair_win_prob": r.get("fair_win_prob"),
                "edge_yes": r.get("edge_yes"),
                "edge_no": r.get("edge_no"),
                "confidence": r.get("confidence"),
                "data_quality": r.get("data_quality"),
                "model_version": r.get("model_version", ""),
                "market_slug": r.get("market_slug", ""),
                "reasons": (r.get("reasons") or [])[:3],
                "ask_yes": r.get("ask_yes"),
                "ask_no": r.get("ask_no"),
                "entry_price": entry_price,
                "current_price": current_price,
                "tp_price": tp_price,
                "sl_price": sl_price,
                "size_usd": size_usd,
                "size_is_estimated": True,
                "unrealized_pnl_dollars": unrealized_pnl_dollars,
                "status_label": status,
                "shadow_label": "Shadow Advisory — Not Executed",
                "resolved": resolved,
                "outcome": yes_resolved,
            })

        return {
            "log_path": str(p),
            "log_age_sec": age_sec,
            "total_lines": len(lines),
            "actionable_count": actionable_count,
            "no_trade_count": no_trade_count,
            "recs": display,
            "pnl": {
                "matched": matched,
                "unresolved": actionable_count - matched,
                "wins": wins,
                "losses": losses,
                "win_rate": round(wins / matched, 4) if matched else None,
                "pnl_units": round(pnl, 4),
                "open_positions": open_count,
                "unrealized_pnl_dollars": round(total_unrealized_dollars, 2),
                "shadow_position_size_usd": default_shadow_size_usd,
            },
        }
    except Exception as exc:
        log.error("mlb_shadow read error: %s", exc)
        return {"error": str(exc), "recs": [], "pnl": {}}


def _build_signals(state: dict) -> list[dict]:
    signals = []
    for pos in (state.get("open_positions") or []):
        slug = pos.get("market_slug", "")
        side = pos.get("side", "BUY_YES")
        entry = float(pos.get("entry_px") or 0)
        conf = float(pos.get("confidence") or 0.6)
        yes_px = entry if "YES" in side else (1 - entry)
        strength = "STRONG" if conf >= 0.72 else ("MODERATE" if conf >= 0.62 else "WEAK")
        signals.append({
            "market_slug": slug,
            "question": slug.replace("-", " ").title(),
            "side": side, "confidence": conf, "yes_price": yes_px,
            "edge_pct": round((conf - yes_px) * 100, 1),
            "signal_strength": strength,
        })
    return signals


# ── HTTP handler ──────────────────────────────────────────────────────────────
DASHBOARD_HTML = Path(__file__).parent / "dashboard.html"
DASHBOARD_V2_HTML = Path(__file__).parent / "dashboard_v2.html"


class DashHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        if "/api/" not in (args[0] if args else ""):
            log.debug(fmt, *args)

    def _cors(self, ct="application/json"):
        self.send_header("Content-Type", ct)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")

    def _json(self, data, status=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self._cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            self._html()
        elif path in ("/dashboard_v2.html", "/v2", "/dashboard-v2"):
            self._html_v2()
        elif path == "/api/state":
            self._json(_read_state())
        elif path == "/api/trades":
            limit = 50
            if "limit=" in self.path:
                try: limit = int(self.path.split("limit=")[1].split("&")[0])
                except Exception: pass
            self._json({"trades": _fetch_trades(limit)})
        elif path == "/api/games":
            with _espn_lock:
                self._json(dict(_espn_scoreboard))
        elif path == "/api/markets":
            self._json({"markets": _read_markets()})
        elif path == "/api/signals":
            self._json({"signals": _build_signals(_read_state())})
        elif path == "/api/candidates":
            self._json({
                "candidates": _read_candidates(),
                "thresholds": {
                    "min_confidence": float(os.getenv("MIN_CONFIDENCE", "0.58")),
                    "max_spread": float(os.getenv("MAX_SPREAD", "0.04")),
                    "min_depth_usd": float(os.getenv("MIN_DEPTH_TOP5_USD", "500")),
                },
            })
        elif path == "/api/mlb-shadow":
            limit = 30
            if "limit=" in self.path:
                try: limit = int(self.path.split("limit=")[1].split("&")[0])
                except Exception: pass
            self._json(_read_mlb_shadow(limit=limit))
        elif path == "/api/bankroll":
            history = _daily_pnl_history()
            # Use full lifetime PnL query — _daily_pnl_history has LIMIT 30 days
            # which would undercount history beyond 30 trading days.
            try:
                with _db() as _bconn:
                    _row = _bconn.execute(
                        "SELECT COALESCE(SUM(pnl_usd),0) FROM trades WHERE status='closed'"
                    ).fetchone()
                net = float(_row[0] or 0.0)
            except Exception:
                net = sum(d["pnl"] for d in history)
            self._json({"start": STARTING_BANKROLL, "current": round(STARTING_BANKROLL + net, 2),
                        "net_pnl": round(net, 2), "history": history})
        elif path == "/api/debug/market-stream":
            self._json(GLOBAL_MARKET_STREAM.debug_status())
        elif path == "/api/stream/state":
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            try:
                for _ in range(30):
                    payload = _stream_positions_mark()
                    self.wfile.write(f"event: positions_mark\ndata: {json.dumps(payload)}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    time.sleep(2)
            except Exception:
                pass
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path.split("?")[0] == "/api/manual-trade":
            length = int(self.headers.get("Content-Length", 0))
            try:
                payload = json.loads(self.rfile.read(length))
            except Exception:
                self._json({"error": "bad json"}, 400); return
            now = datetime.now(timezone.utc).isoformat()
            try:
                with _db() as conn:
                    conn.execute(
                        "INSERT INTO manual_trades (ts_open,market_slug,question,side,entry_px,qty_usd,note,status) "
                        "VALUES (?,?,?,?,?,?,?,'open')",
                        (now, payload.get("market_slug",""), payload.get("question",""),
                         payload.get("side","BUY_YES"), float(payload.get("entry_px") or 0),
                         float(payload.get("qty_usd") or 50), payload.get("note",""))
                    )
                    conn.commit()
                self._json({"ok": True})
            except Exception as exc:
                self._json({"error": str(exc)}, 500)
        else:
            self.send_response(404); self.end_headers()

    def _html(self):
        try:
            content = DASHBOARD_HTML.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_response(404); self.end_headers()
            self.wfile.write(b"dashboard.html not found")

    def _html_v2(self):
        try:
            content = DASHBOARD_V2_HTML.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_response(404); self.end_headers()
            self.wfile.write(b"dashboard_v2.html not found")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    _init_manual_trades_table()

    t = threading.Thread(target=_bg_espn_refresh, daemon=True, name="espn-mlb-refresh")
    t.start()
    log.info("ESPN MLB background refresher started (scoreboard=15s, detail=30s)")

    server = ThreadingHTTPServer(("0.0.0.0", PORT), DashHandler)
    url = f"http://localhost:{PORT}"
    log.info("MLB Dashboard running at %s  (Ctrl-C to stop)", url)

    def _open():
        time.sleep(1.2)
        webbrowser.open(url)

    threading.Thread(target=_open, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Dashboard stopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
