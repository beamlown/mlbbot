"""
core/paper_exec.py — Simulated fill engine for sports_bot_v2
100% sport-agnostic. Interface swappable with live execution.
"""
from __future__ import annotations

import logging
import os

from core.risk import get_risk_packet
from core.types import Market, OBSnapshot, Signal, Trade
from core.utils import now_iso

logger = logging.getLogger("core.paper_exec")

PAPER_FEE_PCT = float(os.getenv("PAPER_FEE_PCT", "0.02"))
PAPER_SLIPPAGE_PCT = float(os.getenv("PAPER_SLIPPAGE_PCT", "0.005"))
PAPER_POSITION_SIZE_USD = float(os.getenv("PAPER_POSITION_SIZE_USD", "50.0"))
CONF_SIZING_ENABLED = os.getenv("CONF_SIZING_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
CONF_TIER_HIGH = float(os.getenv("CONF_TIER_HIGH", "0.70"))
CONF_TIER_VHIGH = float(os.getenv("CONF_TIER_VHIGH", "0.80"))
CONF_SIZE_MID_MULT = float(os.getenv("CONF_SIZE_MID_MULT", "1.25"))
CONF_SIZE_HIGH_MULT = float(os.getenv("CONF_SIZE_HIGH_MULT", "1.50"))
MAX_POSITION_SIZE_USD = float(os.getenv("MAX_POSITION_SIZE_USD", "50"))
RISK_PCT_PER_TRADE = float(os.getenv("RISK_PCT_PER_TRADE", "0.03"))
MIN_POSITION_USD = float(os.getenv("MIN_POSITION_USD", "10.0"))
_PAPER_STARTING_BANKROLL = float(os.getenv("STARTING_BANKROLL", "500"))
PAPER_SLIPPAGE_ENABLED = os.getenv("PAPER_SLIPPAGE_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
PAPER_SLIPPAGE_CENTS = float(os.getenv("PAPER_SLIPPAGE_CENTS", "2.0"))


def _confidence_size(base_usd: float, confidence: float, drawdown_mult: float = 1.0) -> float:
    if base_usd <= 0:
        return 0.0
    if not CONF_SIZING_ENABLED:
        return base_usd * drawdown_mult

    mult = 1.0
    if confidence >= CONF_TIER_VHIGH:
        mult = CONF_SIZE_HIGH_MULT
    elif confidence >= CONF_TIER_HIGH:
        mult = CONF_SIZE_MID_MULT

    sized = base_usd * mult * drawdown_mult
    return max(MIN_POSITION_USD, min(sized, MAX_POSITION_SIZE_USD))


def _walk_the_book(side: str, quantity_usd: float, ask_levels: list[dict]) -> tuple[float, float, bool]:
    """
    Walk the book to compute VWAP for a buy order consuming ask levels.

    Returns: (vwap_price, filled_usd, partial_fill)
    vwap_price = total_usd_spent / total_shares_acquired
    """
    if not ask_levels or quantity_usd <= 0:
        return 0.5, 0.0, True

    filled_usd = 0.0
    total_shares = 0.0

    for level in ask_levels:
        if filled_usd >= quantity_usd:
            break
        try:
            price = float(level.get("price", 0))
            size = float(level.get("size", 0))
            if price <= 0 or size <= 0:
                continue

            remaining_usd = quantity_usd - filled_usd
            level_usd = price * size

            if level_usd <= remaining_usd:
                filled_usd += level_usd
                total_shares += size
            else:
                shares_to_fill = remaining_usd / price
                filled_usd += remaining_usd
                total_shares += shares_to_fill
                break
        except (ValueError, TypeError, KeyError):
            continue

    partial = filled_usd < quantity_usd
    vwap = filled_usd / total_shares if total_shares > 0 else 0.5

    return vwap, filled_usd, partial


def _get_fill_price_with_slippage(vwap: float, is_entry: bool) -> float:
    """Apply slippage buffer on top of VWAP."""
    if not PAPER_SLIPPAGE_ENABLED:
        return vwap

    slippage_dollars = PAPER_SLIPPAGE_CENTS / 100.0
    if is_entry:
        return vwap + slippage_dollars
    else:
        return vwap - slippage_dollars


def _fill_price_entry(side: str, ob: OBSnapshot, size_usd: float = 1.0) -> dict:
    """
    Compute entry fill price using walk-the-book + slippage.

    `size_usd` is the intended order size in USD — walking the book for the
    actual size is critical for thin Polymarket binary books where top-of-book
    depth may be <$10 before the price gaps up.

    Returns: {"fill_px": float, "vwap": float, "partial": bool, "actual_fill_px": float}
    """
    if not PAPER_SLIPPAGE_ENABLED:
        if side == "BUY_YES":
            base = ob.ask_yes or 0.5
        else:
            base = ob.ask_no or 0.5
        return {
            "fill_px": min(0.99, max(0.01, base)),
            "vwap": min(0.99, max(0.01, base)),
            "partial": False,
            "actual_fill_px": min(0.99, max(0.01, base)),
        }

    if side == "BUY_YES":
        ask_levels = ob.ask_levels_yes
        fallback_px = ob.ask_yes or 0.5
    else:
        ask_levels = ob.ask_levels_no
        fallback_px = ob.ask_no or 0.5

    if ask_levels:
        vwap, _, partial = _walk_the_book(side, max(0.01, size_usd), ask_levels)
        if vwap <= 0:
            vwap = fallback_px
    else:
        vwap = fallback_px
        partial = False

    fill_px = _get_fill_price_with_slippage(vwap, is_entry=True)
    fill_px = min(0.99, max(0.01, fill_px))

    return {
        "fill_px": fill_px,
        "vwap": vwap,
        "partial": partial,
        "actual_fill_px": fill_px,
    }


def _fill_price_exit(side: str, ob: OBSnapshot) -> dict:
    """
    Compute exit fill price using walk-the-book + slippage.

    Returns: {"fill_px": float, "vwap": float, "partial": bool, "actual_fill_px": float}
    """
    if not PAPER_SLIPPAGE_ENABLED:
        if side == "BUY_YES":
            base = ob.bid_yes or 0.5
        else:
            base = ob.bid_no or 0.5
        return {
            "fill_px": max(0.01, min(0.99, base)),
            "vwap": max(0.01, min(0.99, base)),
            "partial": False,
            "actual_fill_px": max(0.01, min(0.99, base)),
        }

    if side == "BUY_YES":
        bid_levels = ob.bid_levels_yes
        fallback_px = ob.bid_yes or 0.5
    else:
        bid_levels = ob.bid_levels_no
        fallback_px = ob.bid_no or 0.5

    if bid_levels:
        vwap, _, partial = _walk_the_book(side, 1.0, bid_levels)
        if vwap <= 0:
            vwap = fallback_px
    else:
        vwap = fallback_px
        partial = False

    fill_px = _get_fill_price_with_slippage(vwap, is_entry=False)
    fill_px = max(0.01, min(0.99, fill_px))

    return {
        "fill_px": fill_px,
        "vwap": vwap,
        "partial": partial,
        "actual_fill_px": fill_px,
    }


def _held_bid(side: str, ob: OBSnapshot) -> float | None:
    return ob.bid_yes if side == "BUY_YES" else ob.bid_no


def open_position(
    market: Market,
    signal: Signal,
    ob: OBSnapshot,
    mode: str = "neutral",
    source: str = "bot",
    drawdown_mult: float = 1.0,
) -> Trade:
    recommended_size_usd = signal.components.get("recommended_size_dollars")
    if recommended_size_usd is not None:
        try:
            size_usd = max(MIN_POSITION_USD, min(float(recommended_size_usd), MAX_POSITION_SIZE_USD))
        except Exception:
            logger.warning("SIZING recommended_override parse failed, falling back")
            size_usd = _confidence_size(PAPER_POSITION_SIZE_USD, signal.confidence, drawdown_mult)
        logger.info("SIZING recommended_override=%.2f size_usd=%.2f", float(recommended_size_usd) if recommended_size_usd else 0.0, size_usd)
    else:
        try:
            from core.db import total_realized_pnl as _total_pnl
            _current_bankroll = _PAPER_STARTING_BANKROLL + _total_pnl()
            _bankroll_base = max(MIN_POSITION_USD, _current_bankroll * RISK_PCT_PER_TRADE)
        except Exception:
            logger.warning("SIZING bankroll read failed — falling back to PAPER_POSITION_SIZE_USD")
            _current_bankroll = _PAPER_STARTING_BANKROLL
            _bankroll_base = PAPER_POSITION_SIZE_USD
        size_usd = _confidence_size(_bankroll_base, signal.confidence, drawdown_mult)
        logger.info(
            "SIZING bankroll=%.2f base=%.2f size_usd=%.2f",
            _current_bankroll, _bankroll_base, size_usd,
        )

    fill_result = _fill_price_entry(signal.side, ob, size_usd=size_usd)
    fill_px = fill_result["fill_px"]
    actual_fill_px = fill_result["actual_fill_px"]
    vwap = fill_result["vwap"]
    partial = fill_result["partial"]

    qty = size_usd / fill_px if fill_px > 0 else 0.0
    fees_usd = qty * fill_px * PAPER_FEE_PCT

    held_outcome_label = signal.components.get("held_outcome_label")
    home_team = signal.components.get("home_team")
    away_team = signal.components.get("away_team")
    tracked_team = signal.components.get("tracked_team")
    reasons = signal.components.get("model_reasons") or signal.reasons or []
    freshness = {
        "feature_timestamp": signal.components.get("feature_timestamp"),
        "game_state_timestamp": signal.components.get("game_state_timestamp"),
        "book_timestamp": signal.components.get("book_timestamp"),
        "game_state_age_sec": signal.components.get("game_state_age_sec"),
        "book_age_sec": signal.components.get("book_age_sec"),
        "game_status": signal.components.get("game_status"),
        "inning": signal.components.get("inning"),
        "outs": signal.components.get("outs"),
    }

    trade = Trade(
        id=None,
        ts_open=now_iso(),
        ts_close=None,
        market_slug=market.slug,
        market_id=market.market_id,
        side=signal.side,
        qty=round(qty, 6),
        entry_px=round(fill_px, 6),
        exit_px=None,
        pnl_usd=None,
        fees_usd=round(fees_usd, 6),
        reason_open="",
        reason_close=None,
        confidence=signal.confidence,
        mode=mode,
        status="open",
        source=source,
        actual_fill_px=round(actual_fill_px, 6),
    )

    risk_packet = get_risk_packet(trade, ob=ob, market=market)
    trade.reason_open = (
        f"sig={signal.side} conf={signal.confidence:.3f} "
        f"fv={signal.fair_value_estimate:.3f} mode={mode} "
        f"held={held_outcome_label or ''} "
        f"matchup={(away_team + '@' + home_team) if away_team and home_team else ''} "
        f"tracked={tracked_team or ''} size_usd={round(size_usd, 2)} "
        f"risk={risk_packet} freshness={freshness} reasons={reasons}"
    )

    slippage_bps = round((fill_px - vwap) * 10000) if vwap > 0 else 0
    logger.info(
        "FILL entry | %s | size_usd=%.2f | qty=%.6f | vwap=%.6f | fill_px=%.6f | slippage_bps=%d | partial=%s",
        signal.side, size_usd, qty, vwap, fill_px, slippage_bps, partial
    )

    return trade


def close_position(
    trade: Trade,
    ob: OBSnapshot,
    reason: str,
) -> dict:
    fill_result = _fill_price_exit(trade.side, ob)
    held_exit_px = fill_result["fill_px"]
    vwap = fill_result["vwap"]
    partial = fill_result["partial"]

    entry_px = trade.entry_px or 0.0
    qty = trade.qty or 0.0

    # held-contract gain: exit is bid of the held side minus entry cost
    gross_pnl = (held_exit_px - entry_px) * qty
    exit_fees = qty * held_exit_px * PAPER_FEE_PCT
    entry_fees = trade.fees_usd or 0.0
    net_pnl = gross_pnl - entry_fees - exit_fees

    slippage_bps = round((vwap - held_exit_px) * 10000) if vwap > 0 else 0
    logger.info(
        "FILL exit | %s | qty=%.6f | vwap=%.6f | exit_px=%.6f | slippage_bps=%d | partial=%s",
        trade.side, qty, vwap, held_exit_px, slippage_bps, partial
    )

    return {
        "exit_px": round(held_exit_px, 6),
        "pnl_usd": round(net_pnl, 6),
        "fees_usd": round(entry_fees + exit_fees, 6),
        "ts_close": now_iso(),
        "reason_close": reason,
    }


def mark_to_market_value(trade: Trade, ob: OBSnapshot) -> float:
    if not trade.entry_px or not trade.qty:
        return 0.0
    current_held_price = _held_bid(trade.side, ob)
    if current_held_price is None:
        return 0.0
    if not PAPER_SLIPPAGE_ENABLED:
        held_exit_sim = current_held_price
    else:
        slippage_dollars = PAPER_SLIPPAGE_CENTS / 100.0
        held_exit_sim = current_held_price - slippage_dollars
    held_exit_sim = max(0.01, min(0.99, held_exit_sim))
    return (held_exit_sim - trade.entry_px) * trade.qty
