"""
bot_core.py — Main loop for sports_bot_v2
Multi-sport paper trading bot for Polymarket markets.
Sport selected via SPORT env var: "baseball" (default) or "basketball".
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from core.utils import load_env, atomic_write_json, config_hash, now_iso, append_jsonl, parse_utc_dt

_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_env(str(_ENV_PATH))

# ── Config ────────────────────────────────────────────────────────────────────
SPORT = os.getenv("SPORT", "baseball")
LOOP_SECONDS = int(os.getenv("LOOP_SECONDS", "30"))
DISCOVERY_REFRESH_LOOPS = int(os.getenv("DISCOVERY_REFRESH_LOOPS", "10"))
MAX_SPREAD = float(os.getenv("MAX_SPREAD", "0.04"))
MIN_DEPTH_TOP5_USD = float(os.getenv("MIN_DEPTH_TOP5_USD", "500"))
ENTRY_IMBALANCE_MAX = float(os.getenv("ENTRY_IMBALANCE_MAX", "0.60"))
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.55"))
MAX_CONCURRENT_TRADES = int(os.getenv("MAX_CONCURRENT_TRADES", "3"))
MAX_TRADES_PER_MARKET = int(os.getenv("MAX_TRADES_PER_MARKET", "1"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
STATE_PATH = os.getenv("STATE_PATH", "runtime/state.json")
DB_PATH = os.getenv("DB_PATH", "trades_sports.db")
OB_SNAPSHOTS_DIR = os.getenv("OB_SNAPSHOTS_DIR", "runtime/ob_snapshots")
SESSION_MAX_LOSS_USD = float(os.getenv("SESSION_MAX_LOSS_USD", "0"))
DAILY_MAX_LOSS_USD = float(os.getenv("DAILY_MAX_LOSS_USD", "0"))
SESSION_EXPOSURE_CAP_USD = float(os.getenv("SESSION_EXPOSURE_CAP_USD", "0"))
SESSION_STARTING_BANKROLL_USD = float(os.getenv("SESSION_STARTING_BANKROLL_USD", "500.0"))
STALE_OB_WARN_SECONDS = int(os.getenv("STALE_OB_WARN_SECONDS", "300"))
USE_BATCH_PRICES = os.getenv("USE_BATCH_PRICES", "false").strip().lower() in {"1", "true", "yes", "on"}

BUILD_TAG = f"sports_bot_v2.{SPORT}.2026-03-29"
ENGINE_TAG = f"sports_paper_{SPORT}"

CONFIG_HASH = config_hash([
    "AUTO_STOP_LOSS_PCT",
    "AUTO_TAKE_PROFIT_PCT",
    "DAILY_MAX_LOSS_USD",
    "LATE_INNING_BLOCK",
    "LOOP_SECONDS",
    "MAX_CONCURRENT_TRADES",
    "MAX_SPREAD",
    "MAX_TOTAL_COMMITTED_USD",
    "MAX_TRADES_PER_MARKET",
    "MIN_CONFIDENCE",
    "MIN_DEPTH_TOP5_USD",
    "MIN_ENTRY_CONFIDENCE",
    "MIN_ENTRY_PRICE",
    "PAPER_SLIPPAGE_ENABLED",
    "PAPER_SLIPPAGE_CENTS",
    "SESSION_MAX_LOSS_USD",
    "SPORT",
])

# ── Logging setup ─────────────────────────────────────────────────────────────
Path("logs").mkdir(exist_ok=True)
_log_file = Path("logs") / f"bot_{SPORT}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(_log_file), encoding="utf-8"),
    ],
)
logger = logging.getLogger("bot_core")

# ── Sport adapter injection ────────────────────────────────────────────────────
if SPORT == "baseball":
    from sports.mlb.adapter import (
        SPORT as _SPORT, TOURNAMENT, TAG_SLUG, KEYWORDS, GAME_EVENT_RE,
        extract_teams_from_question, get_game_state, game_signal,
    )
    # MLB player stats enrichment
    from sports.mlb.player_stats import enrich_game_state as _enrich_gs
    _game_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    def prefetch_enrichment(home: str, away: str) -> None:
        """Enrich game state with player stats on discovery."""
        pass  # enrichment happens inside get_game_state call lazily; can pre-warm here
elif SPORT == "basketball":
    from sports.ncaab.adapter import (
        SPORT as _SPORT, TOURNAMENT, TAG_SLUG, KEYWORDS,
        extract_teams_from_question, get_game_state, game_signal,
    )
    GAME_EVENT_RE = None
    _enrich_gs = None
else:
    logger.error("Unknown SPORT=%s. Use 'baseball' or 'basketball'.", SPORT)
    sys.exit(1)

# ── Core module imports (after env load + sport selection) ─────────────────────
from core.db import init_db, insert_open_trade, close_trade, fetch_open_trades, fetch_recent_closed, rolling_stats, total_realized_pnl, total_trade_count, update_trade_attribution

try:
    from dugout_dash.events import GLOBAL_EVENT_BUS as _DUGOUT_BUS
except Exception:
    _DUGOUT_BUS = None
from core.discovery import discover_markets
from core.mode import update_mode, record_closed_trade, get_mode_ctx
from core.orderbook import get_orderbook_snapshot
from core.paper_exec import open_position, close_position, mark_to_market_value, _fill_price_entry
from core.risk import check_entry_gates, check_exit, set_current_loop, NEAR_RESOLUTION_PRICE
from core.attribution import TradeAttribution, write_jsonl, classify_trade
from core.replay_capture import write_capture

LATE_INNING_BLOCK = int(os.getenv("LATE_INNING_BLOCK", "7"))
MAX_SLUG_ENTRIES_SESSION = int(os.getenv("MAX_SLUG_ENTRIES_SESSION", "3"))
from core.types import Market, Trade, Signal
from core.model_bridge import get_approved_intents
from core.market_stream import GLOBAL_MARKET_STREAM


def _build_stream_tracking(markets: list[Market]) -> dict[str, dict[str, str]]:
    tracked: dict[str, dict[str, str]] = {}
    for m in markets:
        if not m.active or m.closed or m.market_type != "moneyline":
            continue
        if m.yes_token_id:
            tracked[f"{m.slug}:yes"] = {
                "asset_id": str(m.yes_token_id),
                "market_id": str(m.market_id),
                "market_slug": str(m.slug),
            }
        if m.no_token_id:
            tracked[f"{m.slug}:no"] = {
                "asset_id": str(m.no_token_id),
                "market_id": str(m.market_id),
                "market_slug": str(m.slug),
            }
    return tracked


def _sync_market_stream(markets: list[Market]) -> None:
    try:
        tracked = _build_stream_tracking(markets)
        changed = GLOBAL_MARKET_STREAM.update_tracked_assets(tracked)
        logger.info(
            "market_stream sync: tracked_assets=%d changed=%s",
            len(tracked),
            changed,
        )
    except Exception as exc:
        logger.warning("market_stream sync failed: %s", exc)


def _refresh_tick_sizes_for_markets(markets: list[Market]) -> None:
    try:
        from core.polymarket_client import refresh_tick_sizes
        token_ids: list[str] = []
        for m in markets:
            if not m.active or m.closed or m.market_type != "moneyline":
                continue
            if m.yes_token_id:
                token_ids.append(str(m.yes_token_id))
            if m.no_token_id:
                token_ids.append(str(m.no_token_id))
        if token_ids:
            n = refresh_tick_sizes(token_ids)
            logger.info("tick_size refresh: requested=%d new_fetches=%d", len(token_ids), n)
    except Exception as exc:
        logger.warning("tick_size refresh failed: %s", exc)


def _batch_ob_scan(markets: list[Market]) -> list[tuple[Market, "OBSnapshot | None", Exception | None]]:
    """Lightweight OB scan using batched midpoints+prices instead of 180 /book GETs.

    Returns the same (market, OBSnapshot, err) tuple shape the per-loop code
    consumes; OBSnapshot here carries best-bid/best-ask/mid, no depth levels.
    Depth is fetched on demand by the single market we're about to trade.

    The caller (`markets` arg) is already filtered — this fn does not re-filter.
    """
    from core.polymarket_client import batch_prices
    from core.types import OBSnapshot

    token_ids: list[str] = []
    for m in markets:
        if m.yes_token_id:
            token_ids.append(str(m.yes_token_id))
        if m.no_token_id:
            token_ids.append(str(m.no_token_id))

    try:
        asks = batch_prices(token_ids, side="SELL")
        bids = batch_prices(token_ids, side="BUY")
    except Exception as exc:
        logger.warning("batch_ob_scan: batched fetch failed err=%s; caller should fall back", exc)
        return [(m, None, exc) for m in markets]

    fetched_at = now_iso()
    out: list[tuple[Market, OBSnapshot | None, Exception | None]] = []
    for m in markets:
        yid, nid = str(m.yes_token_id or ""), str(m.no_token_id or "")
        bid_yes = bids.get(yid)
        ask_yes = asks.get(yid)
        bid_no = bids.get(nid)
        ask_no = asks.get(nid)
        spread_yes = (ask_yes - bid_yes) if (ask_yes is not None and bid_yes is not None) else None
        spread_no = (ask_no - bid_no) if (ask_no is not None and bid_no is not None) else None
        # Compute cheap microstructure checks we CAN do without depth data.
        # Depth check is skipped — batch mode has no levels; trade-time re-fetch covers it.
        micro_ok = True
        micro_reason = ""
        if bid_yes is None or ask_yes is None or bid_no is None or ask_no is None:
            micro_ok = False
            micro_reason = "empty_book"
        elif (spread_yes is not None and spread_yes > MAX_SPREAD) or \
             (spread_no is not None and spread_no > MAX_SPREAD):
            micro_ok = False
            micro_reason = "spread_too_wide"

        ob = OBSnapshot(
            bid_yes=bid_yes,
            ask_yes=ask_yes,
            bid_no=bid_no,
            ask_no=ask_no,
            spread_yes=spread_yes,
            spread_no=spread_no,
            depth_top5_usd_yes=0.0,
            depth_top5_usd_no=0.0,
            imbalance=0.0,
            micro_ok=micro_ok,
            micro_reason=micro_reason,
            fetched_at=fetched_at,
            # bid_levels_* / ask_levels_* default to [] — batch path has no depth;
            # depth_top5_usd_* are 0.0 sentinels — trade-time re-fetches full book.
        )
        out.append((m, ob, None))
    return out


# ── Global state ──────────────────────────────────────────────────────────────
LOOP_COUNT = 0
_markets: list[Market] = []
_guard_block_count = 0
_guard_pass_count = 0
_last_guard_reasons: list[str] = []
_guard_market_blocks: dict[str, int] = defaultdict(int)
_last_invalid_market_details: dict = {}
_market_cooldown: dict[str, float] = {}   # market_id → expiry timestamp
_session_gap_stop_bans: set = set()       # (market_slug, side) → banned for session after gap_stop
_exit_reason_counts: dict[str, int] = defaultdict(int)  # exit reason → count
_resolved_markets: dict = {}
_resolved_markets_mtime: float = 0.0
_session_start_ts = int(time.time())
_session_peak_bankroll: float = SESSION_STARTING_BANKROLL_USD

AUDIT_CANDIDATES_LOG = f"logs/audit_candidates_{SPORT}.jsonl"
TRADE_FORENSICS_LOG = f"logs/trade_forensics_{SPORT}.jsonl"


def _load_resolved_markets() -> dict:
    global _resolved_markets, _resolved_markets_mtime
    p = Path("runtime/resolved_markets.json")
    try:
        mtime = p.stat().st_mtime
        if mtime != _resolved_markets_mtime:
            _resolved_markets = json.loads(p.read_text(encoding="utf-8"))
            _resolved_markets_mtime = mtime
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.debug("resolved_markets load error: %s", e)
    return _resolved_markets


def _write_pid():
    try:
        pid_path = os.path.join(os.path.dirname(STATE_PATH), "bot.pid")
        os.makedirs(os.path.dirname(pid_path), exist_ok=True)
        with open(pid_path, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass


def _write_state(status_line: str = "", mode_ctx=None):
    try:
        open_trades = fetch_open_trades()
        closed_recent = fetch_recent_closed(10)
        realized = total_realized_pnl()
        total = total_trade_count()

        unrealized = 0.0
        open_positions = []
        for t in open_trades:
            try:
                ob = get_orderbook_snapshot(_market_by_id(t.market_id) or _dummy_market(t))
                mtm = mark_to_market_value(t, ob)
                unrealized += mtm
                open_positions.append({
                    "id": t.id,
                    "market_slug": t.market_slug,
                    "market_id": t.market_id,
                    "side": t.side,
                    "entry_px": t.entry_px,
                    "qty": t.qty,
                    "confidence": t.confidence,
                    "pnl_usd": round(mtm, 4),
                    "ts_open": t.ts_open,
                    "source": getattr(t, "source", "bot"),
                })
            except Exception:
                pass

        mode_ctx_local = mode_ctx if mode_ctx is not None else get_mode_ctx()
        r25 = rolling_stats(25)
        r50 = rolling_stats(50)
        r100 = rolling_stats(100)

        total_guard = _guard_block_count + _guard_pass_count
        guard_block_rate = _guard_block_count / total_guard if total_guard > 0 else 0.0

        payload = {
            "engine": ENGINE_TAG,
            "build": BUILD_TAG,
            "sport": SPORT,
            "now": now_iso(),
            "loop_count": LOOP_COUNT,
            "config_hash": CONFIG_HASH,
            "pnl": {
                "realized": round(realized, 4),
                "unrealized": round(unrealized, 4),
                "net": round(realized + unrealized, 4),
                "session_start_ts": _session_start_ts,
            },
            "slots": {
                "open": len(open_trades),
                "max": MAX_CONCURRENT_TRADES,
            },
            "total_trades": total,
            "rolling": {"r25": r25, "r50": r50, "r100": r100},
            "mode": {
                "mode": mode_ctx_local.mode,
                "score": mode_ctx_local.score,
                "dwell_trades": mode_ctx_local.dwell_trades,
                "switch_reason": mode_ctx_local.switch_reason,
                "multipliers": mode_ctx_local.profile_multipliers,
            },
            "guard_block_rate": round(guard_block_rate, 4),
            "guard_reasons": _last_guard_reasons,
            "market_validity_blocks": dict(_guard_market_blocks),
            "invalid_market_blocks": sum(_guard_market_blocks.values()),
            "last_invalid_market_details": _last_invalid_market_details,
            "exit_reason_counts": dict(_exit_reason_counts),
            "market_cooldown_expiry": {
                k: v for k, v in _market_cooldown.items() if v > time.time()
            },
            "market_cooldowns_active": sum(
                1 for exp in _market_cooldown.values() if time.time() < exp
            ),
            "open_positions": open_positions,
            "recent_closed": [
                {
                    "id": t.id,
                    "market_slug": t.market_slug,
                    "side": t.side,
                    "reason_close": t.reason_close,
                    "pnl_usd": t.pnl_usd,
                    "entry_px": t.entry_px,
                    "exit_px": t.exit_px,
                }
                for t in closed_recent
            ],
            "status_line": status_line,
        }
        atomic_write_json(STATE_PATH, payload)
    except Exception as e:
        logger.warning("State write error: %s", e)


def _market_by_id(market_id: str) -> Market | None:
    for m in _markets:
        if m.market_id == market_id:
            return m
    return None


def _dummy_market(trade: Trade) -> Market:
    return Market(
        market_id=trade.market_id,
        event_slug="",
        slug=trade.market_slug,
        question="",
        yes_token_id="",
        no_token_id="",
        start_iso=None,
        end_iso=None,
        sport=SPORT,
        tournament=TOURNAMENT,
    )


def _time_to_end(market: Market) -> float | None:
    end_iso = market.end_iso
    if end_iso and len(end_iso) == 10:
        # Date-only end_iso is local (ET) calendar date. MLB evening games run past
        # midnight UTC, so extend to next-day 08:00 UTC to avoid false negatives.
        from datetime import date, timedelta
        try:
            d = date.fromisoformat(end_iso)
            end_iso = (d + timedelta(days=1)).isoformat() + "T08:00:00+00:00"
        except ValueError:
            end_iso = end_iso + "T23:59:00+00:00"
    end_dt = parse_utc_dt(end_iso)
    if end_dt is None:
        return None
    return (end_dt - datetime.now(timezone.utc)).total_seconds()


def _session_loss_exceeded() -> bool:
    if SESSION_MAX_LOSS_USD <= 0 and DAILY_MAX_LOSS_USD <= 0:
        return False

    closed = fetch_recent_closed(500)

    if SESSION_MAX_LOSS_USD > 0:
        session_pnl = sum(
            float(t.pnl_usd)
            for t in closed
            if t.pnl_usd is not None and t.ts_close and int(t.ts_close) >= _session_start_ts
        )
        if session_pnl <= -SESSION_MAX_LOSS_USD:
            logger.error(
                "SESSION LOSS CAP HIT: session_pnl=%.2f limit=%.2f, blocking all new entries",
                session_pnl,
                SESSION_MAX_LOSS_USD,
            )
            return True

    if DAILY_MAX_LOSS_USD > 0:
        today_start = int(
            datetime.now(timezone.utc)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .timestamp()
        )
        daily_pnl = sum(
            float(t.pnl_usd)
            for t in closed
            if t.pnl_usd is not None and t.ts_close and int(t.ts_close) >= today_start
        )
        if daily_pnl <= -DAILY_MAX_LOSS_USD:
            logger.error(
                "DAILY LOSS CAP HIT: daily_pnl=%.2f limit=%.2f, blocking all new entries",
                daily_pnl,
                DAILY_MAX_LOSS_USD,
            )
            return True

    return False


def _session_exposure_exceeded(open_trades: list) -> bool:
    if SESSION_EXPOSURE_CAP_USD <= 0:
        return False
    open_exposure = sum(
        (t.qty or 0.0) * (t.entry_px or 0.0) for t in open_trades
    )
    if open_exposure >= SESSION_EXPOSURE_CAP_USD:
        logger.warning(
            "Session exposure cap hit: open_exposure=%.2f cap=%.2f — new entry blocked",
            open_exposure,
            SESSION_EXPOSURE_CAP_USD,
        )
        return True
    return False


def main():
    global LOOP_COUNT, _markets, _guard_block_count, _guard_pass_count, _last_guard_reasons, _guard_market_blocks, _last_invalid_market_details

    logger.info("=" * 60)
    logger.info("  sports_bot_v2 starting — sport=%s build=%s", SPORT, BUILD_TAG)
    logger.info("  DB=%s  STATE=%s", DB_PATH, STATE_PATH)
    logger.info("  loop=%ds  max_conc=%d  min_conf=%.2f", LOOP_SECONDS, MAX_CONCURRENT_TRADES, MIN_CONFIDENCE)
    logger.info("=" * 60)

    # Startup proof — emit once per process start for log-based restart verification
    logger.info(
        "STARTUP_PROOF %s",
        json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "pid": os.getpid(),
            "python": sys.executable,
            "cwd": os.getcwd(),
            "env_path": str(_ENV_PATH),
            "config_hash": CONFIG_HASH,
            "gates": {
                "MIN_ENTRY_CONFIDENCE": float(os.getenv("MIN_ENTRY_CONFIDENCE", "0.60")),
                "MIN_ENTRY_PRICE": float(os.getenv("MIN_ENTRY_PRICE", "0.15")),
                "MIN_CONFIDENCE": float(os.getenv("MIN_CONFIDENCE", "0.25")),
                "MAX_CONCURRENT_TRADES": int(os.getenv("MAX_CONCURRENT_TRADES", "3")),
                "MAX_TRADES_PER_MARKET": int(os.getenv("MAX_TRADES_PER_MARKET", "1")),
                "LATE_INNING_BLOCK": int(os.getenv("LATE_INNING_BLOCK", "0")),
                "AUTO_STOP_LOSS_PCT": float(os.getenv("AUTO_STOP_LOSS_PCT", "0.20")),
                "LOOP_SECONDS": int(os.getenv("LOOP_SECONDS", "30")),
                "USE_BATCH_PRICES": USE_BATCH_PRICES,
                "PAPER_SLIPPAGE_ENABLED": os.getenv("PAPER_SLIPPAGE_ENABLED", "true"),
                "PAPER_SLIPPAGE_CENTS": float(os.getenv("PAPER_SLIPPAGE_CENTS", "2.0")),
            },
        }, separators=(",", ":")),
    )

    init_db()
    _write_pid()

    try:
        GLOBAL_MARKET_STREAM.start()
        logger.info("market_stream: client started (websocket thread will connect once assets are tracked)")
    except Exception as exc:
        logger.warning("market_stream: start failed: %s", exc)

    # ── Restore cooldown and session start from prior state ───────────────
    global _market_cooldown, _session_start_ts, _session_gap_stop_bans
    try:
        with open(STATE_PATH) as _f:
            _prior = json.load(_f)
        _now = time.time()
        # Restore cooldown expiry timestamps
        for _mid, _exp in _prior.get("market_cooldown_expiry", {}).items():
            if float(_exp) > _now:
                _market_cooldown[_mid] = float(_exp)
        if _market_cooldown:
            logger.info(
                "Restored %d active market cooldown(s) from prior state",
                len(_market_cooldown),
            )
        # Restore session start so PnL accumulates from true session start, not restart
        _prior_ts = int(((_prior.get("pnl") or {}).get("session_start_ts") or 0))
        if 0 < _prior_ts and (_now - _prior_ts) < 86400:
            _session_start_ts = _prior_ts
            logger.info("Restored session_start_ts=%d from prior state", _session_start_ts)
    except (FileNotFoundError, KeyError, ValueError, TypeError, OSError):
        pass

    Path(OB_SNAPSHOTS_DIR).mkdir(parents=True, exist_ok=True)

    try:
        _markets = discover_markets(
            tag_slug=TAG_SLUG,
            keywords=KEYWORDS,
            sport=_SPORT,
            tournament=TOURNAMENT,
            force_refresh=True,
            game_event_re=GAME_EVENT_RE,
        )
        logger.info("Discovery: %d markets found for %s", len(_markets), SPORT)
        _sync_market_stream(_markets)
        _refresh_tick_sizes_for_markets(_markets)
    except Exception as e:
        logger.error("Initial discovery failed: %s", e)

    try:
        open_trades = fetch_open_trades()
        live_ids = {m.market_id for m in _markets}
        orphans = [t for t in open_trades if t.market_id not in live_ids]
        if orphans:
            logger.warning("Orphaned open trades (no matching live market): %s", [t.market_slug for t in orphans])
    except Exception as e:
        logger.warning("Orphan trade check failed: %s", e)

    while True:
        LOOP_COUNT += 1
        set_current_loop(LOOP_COUNT)
        loop_start = time.monotonic()
        loop_guard_reasons: list[str] = []
        _bridge_consumed_slugs: set[str] = set()

        try:
            r25 = rolling_stats(25)
            mode_ctx = update_mode(r25)

            if LOOP_COUNT % 10 == 0:
                try:
                    _ws_dbg = GLOBAL_MARKET_STREAM.debug_status()
                    logger.info(
                        "market_stream: connected=%s tracked=%d marks=%d parsed_hit=%d parsed_miss=%d reconnects=%d last_msg=%s",
                        _ws_dbg.get("connected"),
                        _ws_dbg.get("tracked_asset_count"),
                        _ws_dbg.get("mark_count_received"),
                        _ws_dbg.get("parser_hit_count"),
                        _ws_dbg.get("parser_miss_count"),
                        _ws_dbg.get("reconnect_count"),
                        _ws_dbg.get("last_message_type"),
                    )
                except Exception as _exc:
                    logger.warning("market_stream debug_status error: %s", _exc)

            if LOOP_COUNT % DISCOVERY_REFRESH_LOOPS == 0:
                try:
                    _markets = discover_markets(
                        tag_slug=TAG_SLUG,
                        keywords=KEYWORDS,
                        sport=_SPORT,
                        tournament=TOURNAMENT,
                        force_refresh=True,
                        game_event_re=GAME_EVENT_RE,
                    )
                    logger.info("Discovery refresh: %d markets", len(_markets))
                    _sync_market_stream(_markets)
                    _refresh_tick_sizes_for_markets(_markets)
                except Exception as e:
                    logger.warning("Discovery refresh failed: %s", e)

            if not _markets:
                logger.info("Loop %d: no markets, sleeping", LOOP_COUNT)
                _write_state(f"loop={LOOP_COUNT} no_markets")
                time.sleep(LOOP_SECONDS)
                continue

            open_trades = fetch_open_trades()
            open_count = len(open_trades)
            open_per_market: dict[str, int] = {}
            for t in open_trades:
                open_per_market[t.market_id] = open_per_market.get(t.market_id, 0) + 1

            loss_cap_hit = _session_loss_exceeded()
            exposure_cap_hit = _session_exposure_exceeded(open_trades)

            # ── Drawdown-aware sizing multiplier ──────────────────────────────
            global _session_peak_bankroll
            _current_equity = SESSION_STARTING_BANKROLL_USD + total_realized_pnl()
            _session_peak_bankroll = max(_session_peak_bankroll, _current_equity)
            if _session_peak_bankroll > 0:
                _drawdown_frac = max(0.0, (_session_peak_bankroll - _current_equity) / _session_peak_bankroll)
            else:
                _drawdown_frac = 0.0
            drawdown_mult = max(0.5, 1.0 - _drawdown_frac)

            # Parallel orderbook scan: 200+ markets × ~1s sequential HTTP = 3+ min
            # per loop, far exceeding LOOP_SECONDS=30. Fan out with a thread pool
            # so signals are processed near-real-time. The CLOB API tolerates
            # ~20 concurrent reads; tune via OB_SCAN_WORKERS env.
            _scan_targets = [
                m for m in _markets
                if m.active and not m.closed and m.market_type != "other"
            ]
            _scan_t0 = time.monotonic()

            if USE_BATCH_PRICES:
                _scan_results = _batch_ob_scan(_scan_targets)
                logger.info(
                    "OB_SCAN (batch) n=%d elapsed=%.2fs",
                    len(_scan_results), time.monotonic() - _scan_t0,
                )
            else:
                _scan_workers = int(os.getenv("OB_SCAN_WORKERS", "20"))

                def _scan_one(market):
                    try:
                        return market, get_orderbook_snapshot(market), None
                    except Exception as e:
                        return market, None, e

                with ThreadPoolExecutor(max_workers=max(1, _scan_workers)) as _pool:
                    _scan_results = list(_pool.map(_scan_one, _scan_targets))

                logger.info(
                    "OB_SCAN n=%d workers=%d elapsed=%.2fs",
                    len(_scan_results), _scan_workers, time.monotonic() - _scan_t0,
                )

            for market, ob, err in _scan_results:
                if err is not None:
                    logger.warning("Market %s error: %s", market.market_id[:12], err)
                    continue
                if ob is None:
                    continue
                try:
                    snap_path = os.path.join(OB_SNAPSHOTS_DIR, f"{market.market_id}.jsonl")
                    append_jsonl(snap_path, {
                        "bid_yes": ob.bid_yes, "ask_yes": ob.ask_yes,
                        "bid_no": ob.bid_no, "ask_no": ob.ask_no,
                        "spread_yes": ob.spread_yes, "spread_no": ob.spread_no,
                        "depth_top5_usd_yes": ob.depth_top5_usd_yes,
                        "depth_top5_usd_no": ob.depth_top5_usd_no,
                        "imbalance": ob.imbalance,
                        "micro_ok": ob.micro_ok,
                        "micro_reason": ob.micro_reason,
                        "fetched_at": ob.fetched_at,
                    })
                except Exception as e:
                    logger.debug("Snap write error %s: %s", market.market_id[:12], e)

                if not ob.micro_ok:
                    loop_guard_reasons.append(f"{market.slug[:20]}:micro_{ob.micro_reason}")
                    _guard_block_count += 1

            # ── Model bridge (paper only) ─────────────────────────────────────
            try:
                _bridge_open_check = fetch_open_trades()
                if loss_cap_hit or exposure_cap_hit:
                    logger.info("BRIDGE SKIP, session/daily loss cap or exposure cap active")
                elif len(_bridge_open_check) >= MAX_CONCURRENT_TRADES:
                    logger.info(
                        "BRIDGE SKIP — at capacity (%d/%d)",
                        len(_bridge_open_check), MAX_CONCURRENT_TRADES,
                    )
                else:
                    open_slugs = {t.market_slug for t in _bridge_open_check}
                    bridge_intents = get_approved_intents(open_slugs)
                    for intent in bridge_intents:
                        current_open = fetch_open_trades()
                        if len(current_open) >= MAX_CONCURRENT_TRADES:
                            logger.info(
                                "BRIDGE CAP HIT — stopping at %d/%d",
                                len(current_open), MAX_CONCURRENT_TRADES,
                            )
                            break
                        current_open_slugs = {t.market_slug for t in current_open}
                        if '_bridge_consumed_slugs' not in locals():
                            _bridge_consumed_slugs = set()
                        if intent["slug"] in _bridge_consumed_slugs:
                            logger.info(
                                "BRIDGE GATE REJECT [loop_slug_dedupe] slug=%s reason=already_consumed_this_loop",
                                intent["slug"],
                            )
                            continue
                        if intent["slug"] in current_open_slugs:
                            logger.info(
                                "BRIDGE RACE SKIP slug=%s reason=slug_opened_by_concurrent_process",
                                intent["slug"],
                            )
                            _bridge_consumed_slugs.add(intent["slug"])
                            continue
                        market = next((m for m in _markets if m.slug == intent["slug"]), None)
                        if market is None:
                            logger.info("BRIDGE GATE REJECT [market_lookup] slug=%s reason=market_not_found", intent["slug"])
                            _bridge_consumed_slugs.add(intent["slug"])
                            continue
                        ob = get_orderbook_snapshot(market)
                        signal = Signal(
                            side=intent["side"],
                            confidence=float(intent.get("confidence") or 0.0),
                            fair_value_estimate=float(intent.get("entry_px") or 0.5),
                            components={
                                "bridge": True,
                                "edge": intent.get("edge"),
                                "held_outcome_label": intent.get("held_outcome_label"),
                                "home_team": intent.get("home_team"),
                                "away_team": intent.get("away_team"),
                                "tracked_team": intent.get("tracked_team"),
                                "tp_price": intent.get("tp_price"),
                                "sl_price": intent.get("sl_price"),
                                "recommended_size_dollars": intent.get("recommended_size_dollars"),
                                "recommended_size_units": intent.get("recommended_size_units"),
                                "model_reasons": intent.get("reasons") or [],
                                "feature_timestamp": intent.get("feature_timestamp"),
                                "game_state_timestamp": intent.get("game_state_timestamp"),
                                "book_timestamp": intent.get("book_timestamp"),
                                "game_state_age_sec": intent.get("game_state_age_sec"),
                                "book_age_sec": intent.get("book_age_sec"),
                                "game_status": intent.get("game_status"),
                                "inning": intent.get("inning"),
                                "inning_half": intent.get("inning_half"),
                                "outs": intent.get("outs"),
                                "market_slug": intent.get("market_slug"),
                                "market_id": intent.get("market_id"),
                            },
                            reasons=["model_bridge"],
                        )
                        _bridge_open_per_market: dict[str, int] = {}
                        for _t in current_open:
                            _bridge_open_per_market[_t.market_id] = _bridge_open_per_market.get(_t.market_id, 0) + 1
                        _intent_inning = intent.get("inning")
                        try:
                            _intent_inning = int(_intent_inning) if _intent_inning is not None else None
                        except (TypeError, ValueError):
                            _intent_inning = None
                        _intent_inning_half = intent.get("inning_half")
                        try:
                            _intent_inning_half = int(_intent_inning_half) if _intent_inning_half is not None else None
                        except (TypeError, ValueError):
                            _intent_inning_half = None
                        # Late-inning policy: allow up through top-of-9th, block
                        # bottom-of-9th and extras. Model is sharpest in late regulation
                        # but bottom-of-9th is walk-off territory and extras are coin
                        # flips. inning_half: 0=top, 1=bottom.
                        _late_inning_block = False
                        _late_reason = ""
                        if _intent_inning is not None:
                            if _intent_inning > 9:
                                _late_inning_block = True
                                _late_reason = f"extras_blocked:inning={_intent_inning}"
                            elif _intent_inning == 9 and _intent_inning_half == 1:
                                _late_inning_block = True
                                _late_reason = "bottom_9th_blocked"
                        if _late_inning_block:
                            logger.info(
                                "BRIDGE GATE REJECT [late_inning_block] slug=%s reason=%s",
                                market.slug, _late_reason,
                            )
                            _guard_block_count += 1
                            loop_guard_reasons.append("bridge:late_inning_block")
                            _bridge_consumed_slugs.add(market.slug)
                            continue
                        _intent_side = intent.get("side", "")
                        if _intent_side and (market.slug, _intent_side) in _session_gap_stop_bans:
                            logger.info(
                                "BRIDGE GATE REJECT [check_entry_gates] slug=%s reasons=%s",
                                market.slug,
                                [f"post_gap_stop_session_ban:{market.slug}:{_intent_side}"],
                            )
                            _guard_block_count += 1
                            loop_guard_reasons.append("bridge:post_gap_stop_session_ban")
                            _bridge_consumed_slugs.add(market.slug)
                            continue
                        if MAX_SLUG_ENTRIES_SESSION > 0:
                            try:
                                import sqlite3 as _sqlite3
                                with _sqlite3.connect(DB_PATH, timeout=2.0) as _sc:
                                    _slug_count = _sc.execute(
                                        "SELECT COUNT(*) FROM trades WHERE market_slug = ? AND date(ts_open) >= date('now', 'localtime')",
                                        (market.slug,),
                                    ).fetchone()[0]
                                if _slug_count >= MAX_SLUG_ENTRIES_SESSION:
                                    logger.info(
                                        "BRIDGE GATE REJECT [check_entry_gates] slug=%s reasons=%s",
                                        market.slug,
                                        [f"session_slug_cap_exceeded:{_slug_count}>={MAX_SLUG_ENTRIES_SESSION}"],
                                    )
                                    _guard_block_count += 1
                                    loop_guard_reasons.append("bridge:session_slug_cap_exceeded")
                                    _bridge_consumed_slugs.add(market.slug)
                                    continue
                            except Exception as _sce:
                                logger.warning("session_slug_cap check failed: %s", _sce)
                        _gate_ok, _gate_reasons = check_entry_gates(
                            ob,
                            signal,
                            mode_ctx,
                            len(current_open),
                            _bridge_open_per_market,
                            market.market_id,
                            _time_to_end(market),
                            market=market,
                            market_cooldown=_market_cooldown,
                        )
                        if not _gate_ok:
                            logger.info(
                                "BRIDGE GATE REJECT [check_entry_gates] slug=%s reasons=%s",
                                market.slug, _gate_reasons,
                            )
                            _guard_block_count += 1
                            loop_guard_reasons.append(f"bridge:{_gate_reasons[0] if _gate_reasons else 'unknown'}")
                            _bridge_consumed_slugs.add(market.slug)
                            try:
                                write_capture({
                                    "ts": now_iso(),
                                    "loop_id": LOOP_COUNT,
                                    "event_slug": market.event_slug or market.slug,
                                    "registry_match": {
                                        "home": signal.components.get("home_team"),
                                        "away": signal.components.get("away_team"),
                                        "status": signal.components.get("game_status"),
                                        "is_live": True,
                                    },
                                    "orderbook": {
                                        "bids": [[ob.bid_yes, 100], [ob.bid_no, 100]] if ob.bid_yes and ob.bid_no else [],
                                        "asks": [[ob.ask_yes, 100], [ob.ask_no, 100]] if ob.ask_yes and ob.ask_no else [],
                                    },
                                    "mark": {
                                        "value": (ob.bid_yes + ob.ask_yes) / 2 if (ob.bid_yes and ob.ask_yes) else None,
                                        "source": "polymarket_ob",
                                        "ts": ob.fetched_at,
                                    },
                                    "model_inputs": {
                                        "home_team": signal.components.get("home_team"),
                                        "away_team": signal.components.get("away_team"),
                                        "inning": signal.components.get("inning"),
                                        "outs": signal.components.get("outs"),
                                        "game_status": signal.components.get("game_status"),
                                        "game_state_age_sec": signal.components.get("game_state_age_sec"),
                                        "feature_timestamp": signal.components.get("feature_timestamp"),
                                    },
                                    "model_output": {
                                        "p_home": None,
                                        "confidence": signal.confidence,
                                        "model_version": "bridge_intent",
                                    },
                                    "discovery_decision": {
                                        "action": "SKIP_GATE",
                                        "reason": _gate_reasons[0] if _gate_reasons else "unknown",
                                    },
                                })
                            except Exception as _ce:
                                logger.debug("Capture write error: %s", _ce)
                            continue
                        # Stale-quote guard: compare the predicted fill price (what
                        # paper_exec will actually pay after walking the thin book) to
                        # the rec's cost. If the live book has drifted more than
                        # BRIDGE_MAX_QUOTE_DRIFT, skip — the signal's edge is gone.
                        # Trade #327 slipped an earlier top-of-book check because
                        # top ask matched, but VWAP walked to 0.99. Use the same
                        # _fill_price_entry paper_exec will use.
                        _bridge_max_drift = float(os.getenv("BRIDGE_MAX_QUOTE_DRIFT", "0.04"))
                        if _bridge_max_drift > 0:
                            _rec_cost = intent.get("market_yes_cost") if intent["side"] == "BUY_YES" else intent.get("market_no_cost")
                            try:
                                _rec_cost = float(_rec_cost) if _rec_cost is not None else None
                            except (TypeError, ValueError):
                                _rec_cost = None
                            # Estimate the trade size the same way paper_exec will so
                            # the predicted VWAP matches what the fill will actually be.
                            _rec_size = intent.get("recommended_size_dollars")
                            try:
                                _guard_size = float(_rec_size) if _rec_size is not None else float(os.getenv("MAX_POSITION_SIZE_USD", "50"))
                            except (TypeError, ValueError):
                                _guard_size = float(os.getenv("MAX_POSITION_SIZE_USD", "50"))
                            try:
                                _predicted_fill = float(_fill_price_entry(intent["side"], ob, size_usd=_guard_size)["fill_px"])
                            except Exception:
                                _predicted_fill = None
                            if _rec_cost is not None and _predicted_fill is not None:
                                _drift = _predicted_fill - _rec_cost
                                if _drift > _bridge_max_drift:
                                    logger.info(
                                        "BRIDGE GATE REJECT [stale_quote] slug=%s reason=predicted_fill=%.4f rec_cost=%.4f drift=%+.4f>%.4f size=%.2f",
                                        market.slug, _predicted_fill, _rec_cost, _drift, _bridge_max_drift, _guard_size,
                                    )
                                    _guard_block_count += 1
                                    loop_guard_reasons.append("bridge:stale_quote")
                                    _bridge_consumed_slugs.add(market.slug)
                                    continue
                        trade = open_position(
                            market,
                            signal,
                            ob,
                            mode=mode_ctx.mode,
                            source="model_bridge",
                        )
                        trade_id = insert_open_trade(trade, sport=SPORT)
                        if trade_id is None:
                            logger.info("BRIDGE OPEN SKIPPED (duplicate slug) slug=%s", market.slug)
                            _bridge_consumed_slugs.add(market.slug)
                            try:
                                write_capture({
                                    "ts": now_iso(),
                                    "loop_id": LOOP_COUNT,
                                    "event_slug": market.event_slug or market.slug,
                                    "registry_match": {
                                        "home": signal.components.get("home_team"),
                                        "away": signal.components.get("away_team"),
                                        "status": signal.components.get("game_status"),
                                        "is_live": True,
                                    },
                                    "orderbook": {
                                        "bids": [[ob.bid_yes, 100], [ob.bid_no, 100]] if ob.bid_yes and ob.bid_no else [],
                                        "asks": [[ob.ask_yes, 100], [ob.ask_no, 100]] if ob.ask_yes and ob.ask_no else [],
                                    },
                                    "mark": {
                                        "value": (ob.bid_yes + ob.ask_yes) / 2 if (ob.bid_yes and ob.ask_yes) else None,
                                        "source": "polymarket_ob",
                                        "ts": ob.fetched_at,
                                    },
                                    "model_inputs": {
                                        "home_team": signal.components.get("home_team"),
                                        "away_team": signal.components.get("away_team"),
                                        "inning": signal.components.get("inning"),
                                        "outs": signal.components.get("outs"),
                                        "game_status": signal.components.get("game_status"),
                                        "game_state_age_sec": signal.components.get("game_state_age_sec"),
                                        "feature_timestamp": signal.components.get("feature_timestamp"),
                                    },
                                    "model_output": {
                                        "p_home": None,
                                        "confidence": signal.confidence,
                                        "model_version": "bridge_intent",
                                    },
                                    "discovery_decision": {
                                        "action": "SKIP_DUPLICATE_SLUG",
                                        "reason": "market_slug already open in session",
                                    },
                                })
                            except Exception as _ce:
                                logger.debug("Capture write error: %s", _ce)
                            continue
                        trade.id = trade_id

                        try:
                            write_capture({
                                "ts": now_iso(),
                                "loop_id": LOOP_COUNT,
                                "event_slug": market.event_slug or market.slug,
                                "registry_match": {
                                    "home": signal.components.get("home_team"),
                                    "away": signal.components.get("away_team"),
                                    "status": signal.components.get("game_status"),
                                    "is_live": True,
                                },
                                "orderbook": {
                                    "bids": [[ob.bid_yes, 100], [ob.bid_no, 100]] if ob.bid_yes and ob.bid_no else [],
                                    "asks": [[ob.ask_yes, 100], [ob.ask_no, 100]] if ob.ask_yes and ob.ask_no else [],
                                },
                                "mark": {
                                    "value": (ob.bid_yes + ob.ask_yes) / 2 if (ob.bid_yes and ob.ask_yes) else None,
                                    "source": "polymarket_ob",
                                    "ts": ob.fetched_at,
                                },
                                "model_inputs": {
                                    "home_team": signal.components.get("home_team"),
                                    "away_team": signal.components.get("away_team"),
                                    "inning": signal.components.get("inning"),
                                    "outs": signal.components.get("outs"),
                                    "game_status": signal.components.get("game_status"),
                                    "game_state_age_sec": signal.components.get("game_state_age_sec"),
                                    "feature_timestamp": signal.components.get("feature_timestamp"),
                                },
                                "model_output": {
                                    "p_home": None,
                                    "confidence": signal.confidence,
                                    "model_version": "bridge_intent",
                                },
                                "discovery_decision": {
                                    "action": "TRADE",
                                    "side": signal.side,
                                    "trade_id": trade_id,
                                },
                            })
                        except Exception as _ce:
                            logger.debug("Capture write error: %s", _ce)

                        # Wire entry attribution
                        try:
                            entry_model_prob = signal.confidence
                            entry_market_prob = ob.ask_yes if signal.side == "BUY_YES" else ob.ask_no
                            if entry_market_prob is None:
                                entry_market_prob = 0.5

                            if entry_model_prob is not None and entry_market_prob is not None:
                                try:
                                    expected_edge_pct = (float(entry_model_prob) - float(entry_market_prob)) * 100.0
                                except (TypeError, ValueError):
                                    expected_edge_pct = None
                            else:
                                expected_edge_pct = None

                            attr = TradeAttribution(
                                trade_id=str(trade_id),
                                entry_model_prob=entry_model_prob,
                                entry_market_prob=entry_market_prob,
                                expected_edge_pct=expected_edge_pct,
                                actual_fill_px=trade.actual_fill_px,
                                actual_fill_size=trade.qty,
                                exit_reason=None,
                                exit_model_prob=None,
                                exit_market_prob=None,
                                hold_seconds=None,
                                resolved_winner=None,
                                model_side_was_right=None,
                                realized_pnl=None,
                                trade_class=None,
                                attribution_version=1,
                            )
                            write_jsonl(attr, Path("logs") / f"attribution_{SPORT}.jsonl")
                            update_trade_attribution(trade_id, {
                                "entry_model_prob": entry_model_prob,
                                "entry_market_prob": entry_market_prob,
                                "expected_edge_pct": expected_edge_pct,
                                "actual_fill_px": trade.actual_fill_px,
                                "actual_fill_size": trade.qty,
                                "attribution_version": 1,
                            })
                        except Exception as _ae:
                            logger.warning("Entry attribution write failed trade=%d: %s", trade_id, _ae)

                        logger.info(
                            "BRIDGE OPEN trade=%d %s %s @ %.4f source=%s",
                            trade_id, market.slug[:30], trade.side, trade.entry_px, trade.source,
                        )
                        try:
                            append_jsonl(TRADE_FORENSICS_LOG, {
                                "trade_id": trade_id,
                                "ts": now_iso(),
                                "slug": market.slug,
                                "side": trade.side,
                                "entry_px": trade.entry_px,
                                "confidence": trade.confidence,
                                "mode": mode_ctx.mode,
                                "config_hash": CONFIG_HASH,
                                "gate_pass": {
                                    "spread_yes": ob.spread_yes,
                                    "spread_no": ob.spread_no,
                                    "depth_top5_yes": ob.depth_top5_usd_yes,
                                    "depth_top5_no": ob.depth_top5_usd_no,
                                    "imbalance": ob.imbalance,
                                    "open_count": len(current_open),
                                    "open_this_market": _bridge_open_per_market.get(market.market_id, 0),
                                    "time_to_end_sec": _time_to_end(market),
                                    "gate_reasons": _gate_reasons,
                                },
                                "game_state": {
                                    "game_status": signal.components.get("game_status"),
                                    "inning": signal.components.get("inning"),
                                    "outs": signal.components.get("outs"),
                                    "game_state_age_sec": signal.components.get("game_state_age_sec"),
                                    "game_state_timestamp": signal.components.get("game_state_timestamp"),
                                    "feature_timestamp": signal.components.get("feature_timestamp"),
                                },
                            })
                        except Exception as _fe:
                            logger.warning("trade_forensics write failed trade=%d: %s", trade_id, _fe)
                        _bridge_consumed_slugs.add(market.slug)
                        if _DUGOUT_BUS is not None:
                            try:
                                _DUGOUT_BUS.publish("trade_entered", {
                                    "trade_id": trade_id,
                                    "slug": trade.market_slug,
                                    "market_id": trade.market_id,
                                    "side": trade.side,
                                    "entry_px": float(trade.entry_px or 0.0),
                                    "qty": float(trade.qty or 0.0),
                                    "size_usd": float(trade.qty or 0.0) * float(trade.entry_px or 0.0),
                                    "confidence": float(trade.confidence or 0.0),
                                    "mode": trade.mode,
                                    "ts": trade.ts_open,
                                    "sport": SPORT,
                                })
                            except Exception as e:
                                logger.warning("dugout bus publish failed (trade_entered): %s", e)
            except Exception as e:
                logger.warning("Model bridge error: %s", e)

            # ── Exit checks ───────────────────────────────────────────────────
            resolved_markets = _load_resolved_markets()
            open_trades = fetch_open_trades()
            for trade in open_trades:
                try:
                    # ── Resolution force-close (market settled on Polymarket) ──
                    res = resolved_markets.get(trade.market_id)
                    if res and res.get("resolved"):
                        if trade.side == "BUY_YES":
                            exit_px = float(res.get("yes_resolution_price", 0.0))
                            resolved_winner = "YES"
                        else:
                            exit_px = float(res.get("no_resolution_price", 0.0))
                            resolved_winner = "NO"
                        pnl = (exit_px - trade.entry_px) * trade.qty

                        # Wire resolution attribution
                        try:
                            model_side_was_right = (resolved_winner == "YES" and trade.side == "BUY_YES") or (resolved_winner == "NO" and trade.side == "BUY_NO")

                            ts_open_dt = parse_utc_dt(trade.ts_open) if trade.ts_open else None
                            hold_seconds = None
                            if ts_open_dt is not None:
                                hold_seconds = int((datetime.now(timezone.utc) - ts_open_dt).total_seconds())

                            trade_class = classify_trade(
                                model_side_was_right=model_side_was_right,
                                expected_edge_pct=None,
                                exit_reason="RESOLUTION",
                                realized_pnl=round(pnl, 4),
                            )

                            update_trade_attribution(trade.id, {
                                "exit_reason": "RESOLUTION",
                                "exit_model_prob": None,
                                "exit_market_prob": exit_px,
                                "hold_seconds": hold_seconds,
                                "resolved_winner": resolved_winner,
                                "model_side_was_right": model_side_was_right,
                                "trade_class": trade_class,
                            })
                        except Exception as _ae:
                            logger.warning("Resolution attribution write failed trade=%d: %s", trade.id, _ae)

                        close_trade(
                            trade.id,
                            {
                                "exit_px": exit_px,
                                "pnl_usd": round(pnl, 4),
                                "fees_usd": 0.0,
                                "reason_close": "market_resolved",
                                "ts_close": int(time.time()),
                            },
                        )
                        record_closed_trade()
                        if _DUGOUT_BUS is not None:
                            try:
                                _DUGOUT_BUS.publish("trade_exited", {
                                    "trade_id": trade.id,
                                    "slug": trade.market_slug,
                                    "side": trade.side,
                                    "entry_px": float(trade.entry_px or 0.0),
                                    "exit_px": float(exit_px or 0.0),
                                    "net_pnl": round(pnl, 4),
                                    "reason": "market_resolved",
                                    "ts": int(time.time()),
                                    "sport": SPORT,
                                })
                            except Exception as e:
                                logger.warning("dugout bus publish failed (trade_exited/resolved): %s", e)
                        _exit_reason_counts["market_resolved"] += 1
                        logger.info(
                            "CLOSE trade=%d %s reason=market_resolved exit_px=%.4f pnl=%.4f",
                            trade.id,
                            trade.market_slug[:25],
                            exit_px,
                            pnl,
                        )
                        continue

                    _mkt_live = _market_by_id(trade.market_id)
                    if _mkt_live is None:
                        logger.warning(
                            "Exit using dummy market for trade=%d market_id=%s — no live discovery match",
                            trade.id, trade.market_id,
                        )
                        mkt = _dummy_market(trade)
                    else:
                        mkt = _mkt_live
                    ob = get_orderbook_snapshot(mkt)
                    t2e = _time_to_end(mkt)

                    should_close, reason = check_exit(trade, ob, t2e)
                    if not should_close and reason == "":
                        _held = ob.bid_yes if trade.side == "BUY_YES" else ob.bid_no
                        if _held is None:
                            logger.warning(
                                "Exit check skipped trade=%d %s reason=empty_ob (held_bid=None)",
                                trade.id, trade.market_slug[:25],
                            )
                            try:
                                _ts_open_dt = parse_utc_dt(str(trade.ts_open)) if trade.ts_open else None
                                if _ts_open_dt is not None:
                                    _stale_secs = time.time() - _ts_open_dt.timestamp()
                                    if _stale_secs > STALE_OB_WARN_SECONDS:
                                        logger.warning(
                                            "STALE OB trade=%d %s stale_secs=%.0f — held_bid=None for >%ds, position may be stuck",
                                            trade.id, trade.market_slug[:25], _stale_secs, STALE_OB_WARN_SECONDS,
                                        )
                            except Exception:
                                pass
                    # ── Hold-to-resolution gate ────────────────────────────
                    # If near_resolution fired but watcher has not confirmed
                    # settlement yet, suppress the exit and hold for full payout.
                    # Safe degradation: if resolved_markets is empty (watcher
                    # not running), fall through to normal near_resolution close.
                    if (should_close
                            and reason == "near_resolution"
                            and resolved_markets  # watcher is running
                            and trade.market_id not in resolved_markets):
                        logger.info(
                            "HOLD trade=%d %s - near resolution, awaiting Polymarket confirmation",
                            trade.id, trade.market_slug[:30],
                        )
                        continue
                    if should_close:
                        close_data = close_position(trade, ob, reason)
                        close_trade(trade.id, close_data)

                        # Wire exit attribution
                        try:
                            ts_open_dt = parse_utc_dt(trade.ts_open) if trade.ts_open else None
                            hold_seconds = None
                            if ts_open_dt is not None:
                                hold_seconds = int((datetime.now(timezone.utc) - ts_open_dt).total_seconds())

                            exit_market_prob = ob.bid_yes if trade.side == "BUY_YES" else ob.bid_no
                            if exit_market_prob is None:
                                exit_market_prob = close_data.get("exit_px", 0.5)

                            realized_pnl = close_data.get("pnl_usd")

                            # Fetch existing entry_model_prob and expected_edge_pct for classification
                            try:
                                import sqlite3 as _sqlite3
                                with _sqlite3.connect(DB_PATH, timeout=2.0) as _conn:
                                    _row = _conn.execute(
                                        "SELECT entry_model_prob, expected_edge_pct FROM trades WHERE id=?",
                                        (trade.id,)
                                    ).fetchone()
                                _entry_model_prob = _row[0] if _row and _row[0] is not None else None
                                _expected_edge_pct = _row[1] if _row and _row[1] is not None else None
                            except Exception:
                                _entry_model_prob = None
                                _expected_edge_pct = None

                            # Classify trade for non-resolution exits (UNRESOLVED, since not resolved by market)
                            trade_class = classify_trade(
                                model_side_was_right=None,
                                expected_edge_pct=_expected_edge_pct,
                                exit_reason=reason,
                                realized_pnl=realized_pnl,
                            )

                            update_trade_attribution(trade.id, {
                                "exit_reason": reason,
                                "exit_model_prob": None,
                                "exit_market_prob": exit_market_prob,
                                "hold_seconds": hold_seconds,
                                "trade_class": trade_class,
                            })
                        except Exception as _ae:
                            logger.warning("Exit attribution write failed trade=%d: %s", trade.id, _ae)

                        record_closed_trade()
                        if _DUGOUT_BUS is not None:
                            try:
                                _DUGOUT_BUS.publish("trade_exited", {
                                    "trade_id": trade.id,
                                    "slug": trade.market_slug,
                                    "side": trade.side,
                                    "entry_px": float(trade.entry_px or 0.0),
                                    "exit_px": float(close_data.get("exit_px") or 0.0),
                                    "net_pnl": float(close_data.get("pnl_usd") or 0.0),
                                    "reason": close_data.get("reason_close") or reason,
                                    "ts": close_data.get("ts_close"),
                                    "sport": SPORT,
                                })
                            except Exception as e:
                                logger.warning("dugout bus publish failed (trade_exited): %s", e)
                        _exit_reason_counts[reason] += 1
                        if reason == "near_resolution":
                            _market_cooldown[trade.market_id] = time.time() + 600
                            logger.info("Cooldown set for market %s (near_resolution exit)", trade.market_slug[:30])
                        elif reason == "stop_loss":
                            _market_cooldown[trade.market_id] = time.time() + 1800
                            logger.info("Cooldown set for market %s (stop_loss exit, 30m)", trade.market_slug[:30])
                        elif reason == "gap_stop":
                            _market_cooldown[trade.market_id] = time.time() + 3600
                            logger.info("Cooldown set for market %s (gap_stop exit, 60m)", trade.market_slug[:30])
                            _session_gap_stop_bans.add((trade.market_slug, trade.side))
                            logger.info(
                                "SESSION BAN [gap_stop] slug=%s side=%s — same-side re-entry blocked for session",
                                trade.market_slug, trade.side,
                            )
                        logger.info(
                            "CLOSE trade=%d %s reason=%s pnl=%.4f",
                            trade.id, trade.market_slug[:25], reason, close_data.get("pnl_usd", 0),
                        )
                except Exception as e:
                    logger.error("Exit check error trade=%d: %s", trade.id, e, exc_info=True)

        except Exception as e:
            logger.error("Loop error: %s", e, exc_info=True)

        # Dedupe guard reasons for state display. Reason strings look like
        # "spread_too_wide:0.0800>0.0400" or "bridge:confidence_too_low:0.3353:0.400" —
        # we want the short name (first token past any "bridge:" or market-slug prefix),
        # not the numeric suffix that split(":")[-1] used to produce.
        seen = []
        for r in loop_guard_reasons:
            parts = r.split(":")
            if not parts:
                key = r
            elif parts[0] == "bridge" and len(parts) > 1:
                key = parts[1]
            elif len(parts) > 1 and parts[0].startswith("mlb-"):
                key = parts[1]  # "mlb-xxx-yyy-date:micro_depth_too_low" → "micro_depth_too_low"
            else:
                key = parts[0]
            if key not in seen:
                seen.append(key)
        _last_guard_reasons = seen[:10]

        _write_state(
            f"loop={LOOP_COUNT} sport={SPORT} mode={mode_ctx.mode} "
            f"open={open_count} guard_block={len(loop_guard_reasons)}",
            mode_ctx=mode_ctx,
        )

        elapsed = time.monotonic() - loop_start
        sleep_for = max(0.0, LOOP_SECONDS - elapsed)
        if sleep_for > 0:
            time.sleep(sleep_for)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Stopped by user (KeyboardInterrupt)")
        sys.exit(0)
