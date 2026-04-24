"""
core/replay_harness.py — Counterfactual replay of historical decisions under alternate configs

Given captured model inputs, orderbooks, and decisions from past discovery loops,
replay the decision pipeline against alternate guardrail configurations to estimate
gate effectiveness and model calibration.

The harness consumes captures from runtime/replay_captures/YYYY-MM-DD.jsonl and
produces a ReplayResult with recomputed trades and attribution.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from core.attribution import TradeAttribution, TradeClass, classify_trade, ExitReason
from core.paper_exec import _walk_the_book, _get_fill_price_with_slippage


@dataclass
class SizingCurve:
    """Configuration for position sizing based on confidence."""
    base_usd: float = 50.0
    confidence_tier_high: float = 0.70
    confidence_tier_vhigh: float = 0.80
    size_mid_mult: float = 1.25
    size_high_mult: float = 1.50
    max_position_usd: float = 100.0
    min_position_usd: float = 10.0


@dataclass
class ReplayConfig:
    """Configuration for a replay run."""
    name: str
    confidence_gate: float
    edge_threshold_pct: float
    sizing: SizingCurve = field(default_factory=SizingCurve)
    slippage_cents: float = 2.0
    model_version: str = "bridge_intent"


@dataclass
class ReplayedTrade:
    """A single trade emitted by the replay harness."""
    trade_id: str
    event_slug: str
    ts_open: str
    ts_close: str | None
    side: str
    qty: float
    entry_px: float
    exit_px: float | None
    pnl_usd: float | None
    entry_model_prob: float | None
    entry_market_prob: float | None
    expected_edge_pct: float | None
    exit_reason: ExitReason | None
    exit_model_prob: float | None
    exit_market_prob: float | None
    hold_seconds: int | None
    resolved_winner: str | None
    model_side_was_right: bool | None
    trade_class: TradeClass | None
    skip_reason: str | None = None


@dataclass
class ReplayResult:
    """Aggregate result of a replay run."""
    config: ReplayConfig
    trades: list[ReplayedTrade] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)
    n_trades: int = 0
    n_skipped: int = 0
    hit_rate: float = 0.0
    brier_score: float = 0.0
    log_loss: float = 0.0
    expected_edge_realized_pct: float = 0.0
    pnl_by_trade_class: dict[TradeClass, float] = field(default_factory=dict)
    total_pnl: float = 0.0


def _compute_confidence_size(confidence: float, sizing: SizingCurve) -> float:
    """Size a position based on confidence and sizing curve."""
    mult = 1.0
    if confidence >= sizing.confidence_tier_vhigh:
        mult = sizing.size_high_mult
    elif confidence >= sizing.confidence_tier_high:
        mult = sizing.size_mid_mult

    sized = sizing.base_usd * mult
    return max(sizing.min_position_usd, min(sized, sizing.max_position_usd))


def _orderbook_to_levels(ob: dict) -> dict[str, list[dict]]:
    """Convert orderbook dict to level format for walk_the_book."""
    levels = {}
    if "bids" in ob:
        levels["bids"] = [{"price": p, "size": s} for p, s in ob["bids"]]
    if "asks" in ob:
        levels["asks"] = [{"price": p, "size": s} for p, s in ob["asks"]]
    return levels


def _compute_mark_prob(mark: dict | None) -> float | None:
    """Extract mark probability from mark snapshot."""
    if not mark or "value" not in mark:
        return None
    return float(mark["value"])


def _should_trade(capture: dict, config: ReplayConfig) -> tuple[bool, str | None]:
    """Decide whether to trade based on config gates."""
    model_output = capture.get("model_output", {})
    confidence = float(model_output.get("confidence", 0.0))

    if confidence < config.confidence_gate:
        return False, f"confidence:{confidence:.3f}<gate:{config.confidence_gate}"

    # Edge threshold: estimated edge in percentage
    # For now, derive edge from model confidence vs mark
    mark = capture.get("mark", {})
    mark_prob = _compute_mark_prob(mark)
    if mark_prob is not None:
        model_prob = float(model_output.get("p_home", 0.5))
        edge_pct = abs(model_prob - mark_prob) * 100.0
        if edge_pct < config.edge_threshold_pct:
            return False, f"edge:{edge_pct:.2f}%<threshold:{config.edge_threshold_pct}%"

    return True, None


def _simulate_fill(
    side: str,
    size_usd: float,
    orderbook: dict,
    slippage_cents: float,
) -> tuple[float, float, bool]:
    """Simulate a fill using orderbook and slippage."""
    levels = _orderbook_to_levels(orderbook)

    # Determine which side of the book we're hitting
    if side in ("BUY_YES", "BUY_NO"):
        ask_key = "asks"
        ask_levels = levels.get(ask_key, [])
        vwap, filled_usd, partial = _walk_the_book(side, size_usd, ask_levels)
    else:
        bid_key = "bids"
        bid_levels = levels.get(bid_key, [])
        vwap, filled_usd, partial = _walk_the_book(side, size_usd, bid_levels)

    # Apply slippage
    fill_px = vwap + (slippage_cents / 100.0)

    return fill_px, filled_usd, partial


def _find_event_closure(
    event_slug: str,
    ts_open: str,
    captures: list[dict],
    start_idx: int,
) -> tuple[bool, str | None, float | None, str | None]:
    """Find market resolution or final price trajectory for an open trade."""
    # Look ahead in captures for the same event
    event_captures = []
    for i in range(start_idx, len(captures)):
        c = captures[i]
        if c.get("event_slug") == event_slug:
            event_captures.append((i, c))

    if not event_captures:
        return False, None, None, None

    # Check if any capture shows market resolved
    for idx, c in event_captures:
        registry = c.get("registry_match", {})
        if registry.get("status") == "FINAL":
            # Market resolved
            mark = c.get("mark", {})
            final_px = _compute_mark_prob(mark) or 0.5
            return True, "RESOLUTION", final_px, c.get("ts")

    # No resolution found - mark as unresolved
    return False, None, None, None


def replay(
    captures_dir: Path,
    start_date: date,
    end_date: date,
    config: ReplayConfig,
) -> ReplayResult:
    """
    Replay captures across a date range under an alternate config.

    Returns a ReplayResult with recomputed trades, attribution, and summary stats.
    """
    result = ReplayResult(config=config)

    # Load captures from date range
    all_captures: list[dict] = []
    from datetime import timedelta
    current_date = start_date
    while current_date <= end_date:
        capture_file = captures_dir / f"{current_date.isoformat()}.jsonl"
        # Also check for .sample.jsonl files for testing
        if capture_file.exists():
            with open(capture_file, "r") as f:
                for line in f:
                    if line.strip():
                        all_captures.append(json.loads(line))
        else:
            # Check for sample file
            sample_file = captures_dir / f"{current_date.isoformat()}.sample.jsonl"
            if sample_file.exists():
                with open(sample_file, "r") as f:
                    for line in f:
                        if line.strip():
                            all_captures.append(json.loads(line))
        current_date = current_date + timedelta(days=1)

    if not all_captures:
        return result

    # Process each capture
    trade_counter = 0
    open_trades: dict[str, ReplayedTrade] = {}

    for capture_idx, capture in enumerate(all_captures):
        event_slug = capture.get("event_slug", "unknown")
        ts = capture.get("ts", datetime.now(timezone.utc).isoformat())

        # Decide whether to trade based on config
        should_trade_decision, skip_reason = _should_trade(capture, config)

        if not should_trade_decision:
            result.skipped.append({
                "event_slug": event_slug,
                "ts": ts,
                "reason": skip_reason,
            })
            result.n_skipped += 1
            continue

        # Simulate fill
        model_output = capture.get("model_output", {})
        discovery_decision = capture.get("discovery_decision", {})
        side = discovery_decision.get("side", "BUY_YES")

        sizing = config.sizing
        size_usd = _compute_confidence_size(
            float(model_output.get("confidence", 0.5)),
            sizing,
        )

        orderbook = capture.get("orderbook", {})
        entry_px, filled_usd, _ = _simulate_fill(side, size_usd, orderbook, config.slippage_cents)

        if filled_usd <= 0:
            continue

        # Estimate entry and mark probabilities
        entry_model_prob = float(model_output.get("p_home", 0.5)) if side == "BUY_YES" else \
                          float(model_output.get("p_away", 0.5))
        entry_market_prob = _compute_mark_prob(capture.get("mark"))

        # Estimate edge at entry
        if entry_market_prob is not None:
            expected_edge_pct = (entry_model_prob - entry_market_prob) * 100.0
        else:
            expected_edge_pct = 0.0

        trade_counter += 1
        trade_id = f"replay_{config.name}_{trade_counter}"

        # Look for closure
        market_resolved, exit_reason, exit_px, ts_close = _find_event_closure(
            event_slug, ts, all_captures, capture_idx + 1
        )

        # Compute PnL
        if exit_px is not None:
            pnl_usd = (exit_px - entry_px) * filled_usd if side == "BUY_YES" else \
                     (entry_px - exit_px) * filled_usd
        else:
            pnl_usd = None
            exit_px = None

        # Determine if model was right
        if market_resolved:
            registry = capture.get("registry_match", {})
            game_result = registry.get("status") == "FINAL"
            # Simplified: assume model was right if edge was positive
            model_side_was_right = expected_edge_pct > 0 if exit_px is not None else None
        else:
            model_side_was_right = None

        # Classify trade
        trade_class = classify_trade(
            model_side_was_right=model_side_was_right,
            expected_edge_pct=expected_edge_pct,
            exit_reason=exit_reason,
            realized_pnl=pnl_usd,
        )

        # Create ReplayedTrade
        hold_seconds = None
        if ts_close and ts:
            try:
                ts_open_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                ts_close_dt = datetime.fromisoformat(ts_close.replace("Z", "+00:00"))
                hold_seconds = int((ts_close_dt - ts_open_dt).total_seconds())
            except (ValueError, AttributeError):
                pass

        trade = ReplayedTrade(
            trade_id=trade_id,
            event_slug=event_slug,
            ts_open=ts,
            ts_close=ts_close,
            side=side,
            qty=filled_usd / entry_px if entry_px > 0 else 0.0,
            entry_px=entry_px,
            exit_px=exit_px,
            pnl_usd=pnl_usd,
            entry_model_prob=entry_model_prob,
            entry_market_prob=entry_market_prob,
            expected_edge_pct=expected_edge_pct,
            exit_reason=exit_reason,
            exit_model_prob=None,  # Would need final model output
            exit_market_prob=exit_px,
            hold_seconds=hold_seconds,
            resolved_winner=None,  # Would extract from registry
            model_side_was_right=model_side_was_right,
            trade_class=trade_class,
        )

        result.trades.append(trade)

    # Compute summary statistics
    result.n_trades = len(result.trades)
    result.n_skipped = len(result.skipped)

    if result.n_trades > 0:
        # Hit rate: winning trades / total trades
        winners = sum(1 for t in result.trades if t.pnl_usd and t.pnl_usd > 0)
        result.hit_rate = winners / result.n_trades

        # PnL by trade class
        pnl_by_class: dict[TradeClass, float] = {}
        for trade in result.trades:
            if trade.trade_class and trade.pnl_usd:
                pnl_by_class[trade.trade_class] = pnl_by_class.get(trade.trade_class, 0.0) + trade.pnl_usd
        result.pnl_by_trade_class = pnl_by_class

        # Total PnL
        result.total_pnl = sum(t.pnl_usd for t in result.trades if t.pnl_usd)

        # Brier score (simplified) and log loss
        predicted_probs = [t.entry_model_prob for t in result.trades if t.entry_model_prob]
        if predicted_probs:
            # Simplified: assume market resolution shows actual outcome
            outcomes = [1.0 if (t.pnl_usd and t.pnl_usd > 0) else 0.0 for t in result.trades]
            if len(predicted_probs) == len(outcomes):
                result.brier_score = sum((p - o) ** 2 for p, o in zip(predicted_probs, outcomes)) / len(outcomes)

        # Expected edge realized
        total_edge = sum(t.expected_edge_pct * (t.qty or 1.0) for t in result.trades if t.expected_edge_pct)
        total_pnl = result.total_pnl or 0.0
        result.expected_edge_realized_pct = (total_pnl / total_edge * 100.0) if total_edge > 0 else 0.0

    return result
