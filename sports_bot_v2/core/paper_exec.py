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
MAX_POSITION_SIZE_USD = float(os.getenv("MAX_POSITION_SIZE_USD", "100"))


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
    return max(0.0, min(sized, MAX_POSITION_SIZE_USD))


def _fill_price_entry(side: str, ob: OBSnapshot) -> float:
    if side == "BUY_YES":
        base = ob.ask_yes or 0.5
    else:
        base = ob.ask_no or 0.5
    fill = base * (1.0 + PAPER_SLIPPAGE_PCT)
    return min(0.99, max(0.01, fill))


def _fill_price_exit(side: str, ob: OBSnapshot) -> float:
    if side == "BUY_YES":
        base = ob.bid_yes or 0.5
    else:
        base = ob.bid_no or 0.5
    fill = base * (1.0 - PAPER_SLIPPAGE_PCT)
    return max(0.01, min(0.99, fill))


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
    fill_px = _fill_price_entry(signal.side, ob)
    recommended_size_usd = signal.components.get("recommended_size_dollars")
    if recommended_size_usd is not None:
        try:
            size_usd = max(0.0, min(float(recommended_size_usd), MAX_POSITION_SIZE_USD))
        except Exception:
            size_usd = _confidence_size(PAPER_POSITION_SIZE_USD, signal.confidence, drawdown_mult)
    else:
        size_usd = _confidence_size(PAPER_POSITION_SIZE_USD, signal.confidence, drawdown_mult)
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

    return trade


def close_position(
    trade: Trade,
    ob: OBSnapshot,
    reason: str,
) -> dict:
    held_exit_px = _fill_price_exit(trade.side, ob)
    entry_px = trade.entry_px or 0.0
    qty = trade.qty or 0.0

    # held-contract gain: exit is bid of the held side minus entry cost
    gross_pnl = (held_exit_px - entry_px) * qty
    exit_fees = qty * held_exit_px * PAPER_FEE_PCT
    entry_fees = trade.fees_usd or 0.0
    net_pnl = gross_pnl - entry_fees - exit_fees

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
    held_exit_sim = current_held_price * (1.0 - PAPER_SLIPPAGE_PCT)
    held_exit_sim = max(0.01, min(0.99, held_exit_sim))
    return (held_exit_sim - trade.entry_px) * trade.qty
