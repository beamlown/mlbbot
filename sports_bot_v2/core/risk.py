"""
core/risk.py — Guard stack gates + exit logic for sports_bot_v2
100% sport-agnostic. v6-style waterfall: fail-fast on first block.
"""
from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

from core.types import Market, ModeCtx, OBSnapshot, Signal, Trade
from core.utils import parse_utc_dt

logger = logging.getLogger("core.risk")

MAX_SPREAD = float(os.getenv("MAX_SPREAD", "0.04"))
MIN_TOUCH_DEPTH_USD = float(os.getenv("MIN_TOUCH_DEPTH_USD", os.getenv("MIN_DEPTH_TOP5_USD", "500")))
ENABLE_MONEYLINES = os.getenv("ENABLE_MONEYLINES", "true").lower() == "true"
ENABLE_SPREADS = os.getenv("ENABLE_SPREADS", "true").lower() == "true"
ENABLE_TOTALS = os.getenv("ENABLE_TOTALS", "true").lower() == "true"
ENTRY_IMBALANCE_MAX = float(os.getenv("ENTRY_IMBALANCE_MAX", "0.60"))
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.55"))
TOTAL_MIN_CONFIDENCE = float(os.getenv("TOTAL_MIN_CONFIDENCE", "0.58"))
MAX_CONCURRENT_TRADES = int(os.getenv("MAX_CONCURRENT_TRADES", "3"))
MAX_TRADES_PER_MARKET = int(os.getenv("MAX_TRADES_PER_MARKET", "1"))
AUTO_TAKE_PROFIT_PCT = float(os.getenv("AUTO_TAKE_PROFIT_PCT", "0.85"))
AUTO_STOP_LOSS_PCT = float(os.getenv("AUTO_STOP_LOSS_PCT", "0.20"))
NEAR_RESOLUTION_PRICE = float(os.getenv("NEAR_RESOLUTION_PRICE", "0.92"))
TRAILING_STOP_ACTIVATE_PCT = float(os.getenv("TRAILING_STOP_ACTIVATE_PCT", "0.15"))
TRAILING_STOP_DRAWDOWN_PCT = float(os.getenv("TRAILING_STOP_DRAWDOWN_PCT", "0.20"))
TIME_EXIT_BUFFER_SECONDS = int(os.getenv("TIME_EXIT_BUFFER_SECONDS", "300"))
SL_CLUSTER_TRIGGER = int(os.getenv("SL_CLUSTER_TRIGGER", "3"))
SL_COOLDOWN_LOOPS = int(os.getenv("SL_COOLDOWN_LOOPS", "5"))
ENTRY_EVENT_MAX_AGE_MINUTES = int(os.getenv("ENTRY_EVENT_MAX_AGE_MINUTES", "300"))
ENTRY_FAIL_CLOSED_ON_MISSING_METADATA = os.getenv("ENTRY_FAIL_CLOSED_ON_MISSING_METADATA", "true").lower() == "true"
MAX_ENTRY_PRICE = float(os.getenv("MAX_ENTRY_PRICE", "0.99"))
MIN_ENTRY_PRICE = float(os.getenv("MIN_ENTRY_PRICE", "0.15"))
MIN_ENTRY_CONFIDENCE = float(os.getenv("MIN_ENTRY_CONFIDENCE", "0.60"))
MAX_TOTAL_COMMITTED_USD = float(os.getenv("MAX_TOTAL_COMMITTED_USD", "150"))

_sl_cluster: list[float] = []
_sl_cooldown_until_loop: int = 0
_current_loop: int = 0
_trade_peak_pct: dict[int, float] = {}


def _held_bid(side: str, ob: OBSnapshot) -> float | None:
    return ob.bid_yes if side == "BUY_YES" else ob.bid_no


def get_committed_usd(trade: Trade) -> float:
    entry_px = trade.entry_px or 0.0
    qty = trade.qty or 0.0
    return entry_px * qty


def get_tp_price(trade: Trade) -> float:
    entry_px = trade.entry_px or 0.0
    return entry_px * (1.0 + AUTO_TAKE_PROFIT_PCT)


def get_sl_price(trade: Trade) -> float:
    entry_px = trade.entry_px or 0.0
    return entry_px * (1.0 - AUTO_STOP_LOSS_PCT)


def get_max_loss_usd(trade: Trade) -> float:
    return (get_sl_price(trade) - (trade.entry_px or 0.0)) * (trade.qty or 0.0)


def parse_backed_faded_teams(market_slug: str, side: str) -> tuple[str | None, str | None]:
    m = re.match(r"^[A-Za-z0-9_]+-([A-Za-z0-9_]+)-([A-Za-z0-9_]+)-\d{4}-\d{2}-\d{2}$", market_slug)
    if not m:
        return None, None
    team_yes = m.group(1).upper()
    team_no = m.group(2).upper()
    if side == "BUY_YES":
        return team_yes, team_no
    return team_no, team_yes


def get_current_held_price(trade: Trade, ob: OBSnapshot) -> float | None:
    return _held_bid(trade.side, ob)


def get_held_token_id(trade: Trade, market: Market | None = None) -> str | None:
    if market is None:
        return None
    return market.yes_token_id if trade.side == "BUY_YES" else market.no_token_id


def get_risk_packet(trade: Trade, ob: OBSnapshot | None = None, market: Market | None = None) -> dict[str, Any]:
    backed_team, faded_team = parse_backed_faded_teams(trade.market_slug, trade.side)
    return {
        "entry_px": trade.entry_px,
        "qty": trade.qty,
        "committed_usd": get_committed_usd(trade),
        "tp_price": get_tp_price(trade),
        "sl_price": get_sl_price(trade),
        "max_loss_usd": get_max_loss_usd(trade),
        "held_token_id": get_held_token_id(trade, market),
        "backed_team": backed_team,
        "faded_team": faded_team,
        "current_held_price": get_current_held_price(trade, ob) if ob is not None else None,
    }


def set_current_loop(n: int) -> None:
    global _current_loop
    _current_loop = n


def record_stop_loss() -> None:
    global _sl_cooldown_until_loop
    _sl_cluster.append(time.time())
    while len(_sl_cluster) > SL_CLUSTER_TRIGGER + 1:
        _sl_cluster.pop(0)
    recent = [t for t in _sl_cluster if time.time() - t < 300]
    if len(recent) >= SL_CLUSTER_TRIGGER:
        _sl_cooldown_until_loop = _current_loop + SL_COOLDOWN_LOOPS
        logger.warning("SL cluster detected (%d stops) — cooldown for %d loops", len(recent), SL_COOLDOWN_LOOPS)


def validate_market_tradeable_now(market: Market, time_to_end: float | None) -> tuple[bool, str]:
    if market.resolved:
        return False, "guard_market_resolved"
    if market.closed:
        return False, "guard_market_closed"
    if not market.active:
        return False, "guard_market_not_active"
    if time_to_end is not None and time_to_end < 0:
        return False, "guard_market_ended"
    if time_to_end is None and ENTRY_FAIL_CLOSED_ON_MISSING_METADATA:
        return False, "guard_market_missing_metadata"
    if ENTRY_EVENT_MAX_AGE_MINUTES > 0 and market.start_iso:
        start_dt = parse_utc_dt(market.start_iso)
        if start_dt is not None:
            age_minutes = (datetime.now(timezone.utc) - start_dt).total_seconds() / 60.0
            if age_minutes > ENTRY_EVENT_MAX_AGE_MINUTES:
                return False, "guard_market_too_old"
    return True, ""


def check_entry_gates(
    ob: OBSnapshot,
    sig: Signal,
    mode_ctx: ModeCtx,
    open_count: int,
    open_per_market: dict[str, int],
    market_id: str,
    time_to_end_seconds: float | None,
    market: Market | None = None,
    market_cooldown: dict[str, float] | None = None,
) -> tuple[bool, list[str]]:
    """Waterfall guard stack. Returns (all_ok, [reasons]). Stops at first block."""
    import time as _t

    # Hard confidence floor — checked first, before any DB or OB work
    if MIN_ENTRY_CONFIDENCE > 0.0:
        signal_confidence = getattr(sig, "confidence", None)
        if signal_confidence is None or signal_confidence < MIN_ENTRY_CONFIDENCE:
            return False, [f"confidence_too_low:{signal_confidence}:{MIN_ENTRY_CONFIDENCE:.3f}"]

    mults = mode_ctx.profile_multipliers
    eff_max_spread = MAX_SPREAD * mults.get("max_spread", 1.0)
    eff_min_depth = MIN_TOUCH_DEPTH_USD * mults.get("min_depth_usd", 1.0)
    eff_min_conf = MIN_CONFIDENCE * mults.get("min_confidence", 1.0)
    if market is not None and market.market_type == "total":
        eff_min_conf = max(eff_min_conf, TOTAL_MIN_CONFIDENCE)
    eff_max_conc = int(mults.get("max_concurrent", MAX_CONCURRENT_TRADES))

    # A1 — market type enable/disable gates
    if market is not None:
        if market.market_type == "total" and not ENABLE_TOTALS:
            return False, ["totals_disabled"]
        if market.market_type == "spread" and not ENABLE_SPREADS:
            return False, ["spreads_disabled"]
        if market.market_type == "moneyline" and not ENABLE_MONEYLINES:
            return False, ["moneylines_disabled"]

    if ob.spread_yes is not None and ob.spread_yes > eff_max_spread:
        return False, [f"spread_too_wide:{ob.spread_yes:.4f}>{eff_max_spread:.4f}"]

    if sig.side == "BUY_YES" and ob.ask_yes is not None and ob.ask_yes >= MAX_ENTRY_PRICE:
        return False, [f"entry_price_too_high:{ob.ask_yes:.4f}>={MAX_ENTRY_PRICE:.4f}"]
    if sig.side == "BUY_NO" and ob.ask_no is not None and ob.ask_no >= MAX_ENTRY_PRICE:
        return False, [f"entry_price_too_high:{ob.ask_no:.4f}>={MAX_ENTRY_PRICE:.4f}"]

    ask_side = ob.ask_yes if sig.side == "BUY_YES" else ob.ask_no
    if ask_side is not None and ask_side < MIN_ENTRY_PRICE:
        return False, [f"entry_price_too_low:{ask_side:.4f}<{MIN_ENTRY_PRICE:.4f}"]

    # Block entry if the market is already near resolution — entering here just locks in a loss
    if sig.side == "BUY_YES" and ob.bid_yes is not None and ob.bid_yes >= NEAR_RESOLUTION_PRICE:
        return False, [f"near_resolution_entry:bid_yes={ob.bid_yes:.4f}>={NEAR_RESOLUTION_PRICE:.4f}"]
    if sig.side == "BUY_NO" and ob.bid_no is not None and ob.bid_no >= NEAR_RESOLUTION_PRICE:
        return False, [f"near_resolution_entry:bid_no={ob.bid_no:.4f}>={NEAR_RESOLUTION_PRICE:.4f}"]

    depth = min(ob.depth_top5_usd_yes, ob.depth_top5_usd_no)
    if depth < eff_min_depth:
        return False, [f"depth_too_low:{depth:.1f}<{eff_min_depth:.1f}"]

    if abs(ob.imbalance) > ENTRY_IMBALANCE_MAX:
        return False, [f"imbalance_extreme:{ob.imbalance:.3f}>{ENTRY_IMBALANCE_MAX}"]

    if sig.confidence < eff_min_conf:
        return False, [f"confidence_low:{sig.confidence:.3f}<{eff_min_conf:.3f}"]

    if sig.side == "NONE":
        return False, ["signal_none"]

    if open_count >= eff_max_conc:
        return False, [f"max_concurrent:{open_count}>={eff_max_conc}"]

    market_open = open_per_market.get(market_id, 0)
    if market_open >= MAX_TRADES_PER_MARKET:
        return False, [f"max_per_market:{market_open}>={MAX_TRADES_PER_MARKET}"]

    if MAX_TOTAL_COMMITTED_USD > 0:
        try:
            import sqlite3 as _sqlite3
            _db_path = os.getenv("DB_PATH", "trades_sports.db")
            with _sqlite3.connect(_db_path, timeout=2.0) as _conn:
                _row = _conn.execute(
                    "SELECT COALESCE(SUM(entry_px * qty), 0) FROM trades WHERE status='open'"
                ).fetchone()
            _committed = float(_row[0] or 0)
            _max_new = float(os.getenv("MAX_POSITION_SIZE_USD", "50"))
            if _committed + _max_new > MAX_TOTAL_COMMITTED_USD:
                return False, [f"exposure_cap_exceeded:committed={_committed:.2f}+{_max_new:.2f}>{MAX_TOTAL_COMMITTED_USD:.2f}"]
        except Exception as _e:
            logger.warning("exposure_cap check failed: %s", _e)

    if _sl_cooldown_until_loop > _current_loop:
        remaining = _sl_cooldown_until_loop - _current_loop
        return False, [f"sl_cluster_cooldown:{remaining}_loops_remaining"]

    if time_to_end_seconds is not None and time_to_end_seconds < TIME_EXIT_BUFFER_SECONDS * 2:
        return False, [f"too_close_to_end:{time_to_end_seconds:.0f}s<{TIME_EXIT_BUFFER_SECONDS*2}s"]

    if market_cooldown is not None and market_id in market_cooldown:
        if _t.time() < market_cooldown[market_id]:
            return False, ["market_cooldown"]

    if market is not None:
        valid, validity_reason = validate_market_tradeable_now(market, time_to_end_seconds)
        if not valid:
            return False, [validity_reason]

    return True, []


def check_exit(
    trade: Trade,
    ob: OBSnapshot,
    time_to_end_seconds: float | None = None,
) -> tuple[bool, str]:
    if trade.entry_px is None or trade.entry_px <= 0:
        return False, ""

    current_held_price = _held_bid(trade.side, ob)
    if current_held_price is None:
        return False, ""

    held_unrealized_pct = (current_held_price - trade.entry_px) / trade.entry_px
    tp_price = get_tp_price(trade)
    sl_price = get_sl_price(trade)

    gap_threshold = AUTO_STOP_LOSS_PCT * 2.0
    if held_unrealized_pct < -gap_threshold:
        _trade_peak_pct.pop(trade.id, None)
        return True, "gap_stop"

    if current_held_price >= NEAR_RESOLUTION_PRICE:
        _trade_peak_pct.pop(trade.id, None)
        return True, "near_resolution"

    if current_held_price >= tp_price:
        _trade_peak_pct.pop(trade.id, None)
        return True, "take_profit"

    if trade.id is not None:
        prev_peak = _trade_peak_pct.get(trade.id, 0.0)
        new_peak = max(prev_peak, held_unrealized_pct)
        _trade_peak_pct[trade.id] = new_peak

        if new_peak >= TRAILING_STOP_ACTIVATE_PCT:
            drawdown_from_peak = new_peak - held_unrealized_pct
            if drawdown_from_peak >= TRAILING_STOP_DRAWDOWN_PCT:
                _trade_peak_pct.pop(trade.id, None)
                return True, f"trailing_stop(peak={new_peak:.0%},now={held_unrealized_pct:.0%})"

    if current_held_price <= sl_price:
        record_stop_loss()
        _trade_peak_pct.pop(trade.id, None)
        return True, "stop_loss"

    if time_to_end_seconds is not None and time_to_end_seconds < TIME_EXIT_BUFFER_SECONDS:
        return True, "time_exit"

    return False, ""


def mark_to_market(trade: Trade, ob: OBSnapshot) -> float:
    if trade.entry_px is None or trade.qty is None:
        return 0.0
    current_held_price = _held_bid(trade.side, ob)
    if current_held_price is None:
        return 0.0
    return (current_held_price - trade.entry_px) * trade.qty
