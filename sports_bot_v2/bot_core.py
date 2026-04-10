"""
bot_core.py — Main loop for sports_bot_v2
Multi-sport paper trading bot for Polymarket markets.
Sport selected via SPORT env var: "baseball" (default) or "basketball".
"""
from __future__ import annotations

import logging
import os
import sys
import time
from collections import defaultdict
from datetime import date as _date, datetime, timezone
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

BUILD_TAG = f"sports_bot_v2.{SPORT}.2026-03-29"
ENGINE_TAG = f"sports_paper_{SPORT}"

CONFIG_HASH = config_hash([
    "SPORT", "LOOP_SECONDS", "MAX_SPREAD", "MIN_DEPTH_TOP5_USD", "MIN_CONFIDENCE",
    "AUTO_TAKE_PROFIT_PCT", "AUTO_STOP_LOSS_PCT", "MAX_CONCURRENT_TRADES",
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
from core.db import init_db, insert_open_trade, close_trade, fetch_open_trades, fetch_recent_closed, rolling_stats, total_realized_pnl, total_trade_count
from core.discovery import discover_markets
from core.mode import update_mode, record_closed_trade, get_mode_ctx
from core.orderbook import get_orderbook_snapshot
from core.paper_exec import open_position, close_position, mark_to_market_value
from core.risk import check_entry_gates, check_exit, set_current_loop, NEAR_RESOLUTION_PRICE
from core.signal_base import generate_signal
from core.types import Market, Trade, Signal
from core.model_bridge import get_approved_intents

# ── Global state ──────────────────────────────────────────────────────────────
LOOP_COUNT = 0
_markets: list[Market] = []
_guard_block_count = 0
_guard_pass_count = 0
_last_guard_reasons: list[str] = []
_guard_market_blocks: dict[str, int] = defaultdict(int)
_last_invalid_market_details: dict = {}
_market_cooldown: dict[str, float] = {}   # market_id → expiry timestamp
_exit_reason_counts: dict[str, int] = defaultdict(int)  # exit reason → count

AUDIT_CANDIDATES_LOG = f"logs/audit_candidates_{SPORT}.jsonl"
ALLOW_LOCAL_MLB_ORIGINATION = os.getenv("ALLOW_LOCAL_MLB_ORIGINATION", "0") == "1"


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


def main():
    global LOOP_COUNT, _markets, _guard_block_count, _guard_pass_count, _last_guard_reasons, _guard_market_blocks, _last_invalid_market_details

    logger.info("=" * 60)
    logger.info("  sports_bot_v2 starting — sport=%s build=%s", SPORT, BUILD_TAG)
    logger.info("  DB=%s  STATE=%s", DB_PATH, STATE_PATH)
    logger.info("  loop=%ds  max_conc=%d  min_conf=%.2f", LOOP_SECONDS, MAX_CONCURRENT_TRADES, MIN_CONFIDENCE)
    logger.info("=" * 60)

    init_db()
    _write_pid()
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

        try:
            r25 = rolling_stats(25)
            mode_ctx = update_mode(r25)

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

            for market in _markets:
                if not market.active or market.closed:
                    continue
                if market.market_type == "other":
                    continue

                try:
                    ob = get_orderbook_snapshot(market)

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

                    if not ob.micro_ok:
                        loop_guard_reasons.append(f"{market.slug[:20]}:micro_{ob.micro_reason}")
                        _guard_block_count += 1
                        continue

                    # Generate signal using sport-injected functions
                    if not ALLOW_LOCAL_MLB_ORIGINATION:
                        logger.debug(
                            "LOCAL MLB ORIGINATION DISABLED slug=%s reason=model_authority_enforced",
                            market.slug,
                        )
                        continue

                    # Date gate: only bet on today's games (same check as model_bridge.py line 127)
                    try:
                        _slug_parts = market.slug.split('-')
                        _slug_date = _date.fromisoformat('-'.join(_slug_parts[-3:]))
                    except Exception:
                        _slug_date = None
                    if _slug_date != _date.today():
                        logger.debug('LOCAL DATE GATE REJECT slug=%s slug_date=%s today=%s', market.slug, _slug_date, _date.today())
                        continue

                    sig = generate_signal(
                        market=market,
                        ob=ob,
                        extract_teams_fn=extract_teams_from_question,
                        get_game_state_fn=get_game_state,
                        game_signal_fn=game_signal,
                    )
                    t2e = _time_to_end(market)

                    gates_ok, gate_reasons = check_entry_gates(
                        ob=ob, sig=sig, mode_ctx=mode_ctx,
                        open_count=open_count,
                        open_per_market=open_per_market,
                        market_id=market.market_id,
                        time_to_end_seconds=t2e,
                        market=market,
                        market_cooldown=_market_cooldown,
                    )

                    # A5 — decision quality telemetry
                    _gc = sig.components.get("game_context", {})
                    _audit_rec = {
                        "ts": now_iso(),
                        "loop": LOOP_COUNT,
                        "sport": SPORT,
                        "market_id": market.market_id,
                        "market_type": market.market_type,
                        "slug": market.slug,
                        "event": market.question[:60],
                        "side": sig.side,
                        "confidence": round(sig.confidence, 4),
                        "eligible": gates_ok,
                        "reject_reason": gate_reasons[0] if not gates_ok and gate_reasons else "",
                        "ob_snapshot": {
                            "bid_yes": ob.bid_yes,
                            "ask_yes": ob.ask_yes,
                            "spread_yes": ob.spread_yes,
                            "thin_side_depth_usd": ob.depth_top5_usd_yes,
                            "depth_usd_no": ob.depth_top5_usd_no,
                            "imbalance": ob.imbalance,
                        },
                        "signal": {
                            "raw_score": sig.components.get("raw_score"),
                            "game_score": _gc.get("score"),
                            "game_reason": _gc.get("reason"),
                            "sharp_edge": _gc.get("sharp_edge"),
                            "sharp_score": _gc.get("sharp_score"),
                            "game_inning": _gc.get("inning"),
                            "game_outs": _gc.get("outs"),
                            "game_score_state": _gc.get("score"),
                            "weights": sig.components.get("weights"),
                        },
                    }
                    try:
                        append_jsonl(AUDIT_CANDIDATES_LOG, _audit_rec)
                    except Exception:
                        pass

                    if not gates_ok:
                        reason_str = gate_reasons[0] if gate_reasons else "unknown"
                        loop_guard_reasons.append(f"{market.slug[:20]}:{reason_str}")
                        _guard_block_count += 1
                        if reason_str.startswith("guard_market_"):
                            _guard_market_blocks[reason_str] += 1
                            _last_invalid_market_details = {
                                "ts": now_iso(),
                                "slug": market.slug,
                                "market_id": market.market_id,
                                "reason": reason_str,
                                "active": market.active,
                                "closed": market.closed,
                                "resolved": market.resolved,
                                "end_iso": market.end_iso,
                                "start_iso": market.start_iso,
                                "time_to_end_sec": t2e,
                            }
                        logger.debug("Guard block [%s]: %s", market.slug[:30], reason_str)
                        continue

                    _guard_pass_count += 1

                    trade = open_position(market, sig, ob, mode=mode_ctx.mode)
                    trade_id = insert_open_trade(trade, sport=SPORT)
                    if trade_id is None:
                        logger.info("OPEN SKIPPED (duplicate slug) slug=%s", market.slug)
                        continue
                    trade.id = trade_id
                    open_count += 1
                    open_per_market[market.market_id] = open_per_market.get(market.market_id, 0) + 1

                    logger.info(
                        "OPEN trade=%d %s %s @ %.4f conf=%.3f",
                        trade_id, market.slug[:30], sig.side, trade.entry_px, sig.confidence,
                    )

                except Exception as e:
                    logger.warning("Market %s error: %s", market.market_id[:12], e)

            # ── Model bridge (paper only) ─────────────────────────────────────
            try:
                _bridge_open_check = fetch_open_trades()
                if len(_bridge_open_check) >= MAX_CONCURRENT_TRADES:
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
                        if intent["slug"] in current_open_slugs:
                            logger.info(
                                "BRIDGE RACE SKIP slug=%s reason=slug_opened_by_concurrent_process",
                                intent["slug"],
                            )
                            continue
                        market = next((m for m in _markets if m.slug == intent["slug"]), None)
                        if market is None:
                            logger.info("BRIDGE GATE REJECT [market_lookup] slug=%s reason=market_not_found", intent["slug"])
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
                                "outs": intent.get("outs"),
                                "market_slug": intent.get("market_slug"),
                                "market_id": intent.get("market_id"),
                            },
                            reasons=["model_bridge"],
                        )
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
                            continue
                        trade.id = trade_id
                        logger.info(
                            "BRIDGE OPEN trade=%d %s %s @ %.4f source=%s",
                            trade_id, market.slug[:30], trade.side, trade.entry_px, trade.source,
                        )
            except Exception as e:
                logger.warning("Model bridge error: %s", e)

            # ── Exit checks ───────────────────────────────────────────────────
            open_trades = fetch_open_trades()
            for trade in open_trades:
                try:
                    mkt = _market_by_id(trade.market_id) or _dummy_market(trade)
                    ob = get_orderbook_snapshot(mkt)
                    t2e = _time_to_end(mkt)

                    should_close, reason = check_exit(trade, ob, t2e)
                    if should_close:
                        close_data = close_position(trade, ob, reason)
                        close_trade(trade.id, close_data)
                        record_closed_trade()
                        _exit_reason_counts[reason] += 1
                        if reason == "near_resolution":
                            _market_cooldown[trade.market_id] = time.time() + 600
                            logger.info(
                                "Cooldown set for market %s (near_resolution exit)", trade.market_slug[:30]
                            )
                        logger.info(
                            "CLOSE trade=%d %s reason=%s pnl=%.4f",
                            trade.id, trade.market_slug[:25], reason, close_data.get("pnl_usd", 0),
                        )
                except Exception as e:
                    logger.warning("Exit check error trade=%s: %s", trade.id, e)

        except Exception as e:
            logger.error("Loop error: %s", e, exc_info=True)

        seen = []
        for r in loop_guard_reasons:
            key = r.split(":")[-1] if ":" in r else r
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
