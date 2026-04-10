"""
core/signal_base.py — Orderbook microstructure signal components
Sport-agnostic: momentum, mean reversion, imbalance, spread quality.
Game context is dispatched to sport-specific modules.
"""
from __future__ import annotations

import logging
import os
import time
from collections import deque
from typing import Any, Callable

from core.types import Market, OBSnapshot, Signal

logger = logging.getLogger("core.signal_base")

# Rolling price cache per market
_PRICE_HISTORY: dict[str, deque] = {}
_PRICE_HISTORY_MAX = 20

# OB component weights (normalized against each other, then scaled by 1-w_game)
W_MOMENTUM = float(os.getenv("SIG_W_MOMENTUM", "0.30"))
W_MEAN_REVERT = float(os.getenv("SIG_W_MEAN_REVERT", "0.20"))
W_IMBALANCE = float(os.getenv("SIG_W_IMBALANCE", "0.25"))

# Game context weights per market type (overridden by sport adapter env vars)
W_GAME_MONEYLINE = float(os.getenv("SIG_W_GAME_MONEYLINE", "0.25"))
W_GAME_SPREAD = float(os.getenv("SIG_W_GAME_SPREAD", "0.40"))
W_GAME_TOTAL = float(os.getenv("SIG_W_GAME_TOTAL", "0.40"))

MOMENTUM_MIN_SAMPLES = int(os.getenv("MOMENTUM_MIN_SAMPLES", "4"))
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.55"))
MEAN_REVERT_EXTREME_THRESHOLD = float(os.getenv("SIG_MEAN_REVERT_EXTREME_THRESHOLD", "0.4"))
LIVE_WARMUP_SECONDS = int(os.getenv("LIVE_WARMUP_SECONDS", "90"))

# Track when each market first went live (for warmup window)
_MARKET_FIRST_LIVE: dict[str, float] = {}

# All statuses considered "live" across all sports
LIVE_STATUSES = {
    # NCAAB
    "FIRST_HALF", "HALFTIME", "SECOND_HALF", "OVERTIME",
    # MLB
    "EARLY_INNINGS", "MID_GAME", "LATE_GAME", "EXTRAS",
    # Generic
    "LIVE",
}


def _update_price_history(market_id: str, ob: OBSnapshot) -> deque:
    if market_id not in _PRICE_HISTORY:
        _PRICE_HISTORY[market_id] = deque(maxlen=_PRICE_HISTORY_MAX)
    if ob.ask_yes is not None:
        _PRICE_HISTORY[market_id].append(ob.ask_yes)
    return _PRICE_HISTORY[market_id]


def _momentum_score(history: deque) -> tuple[float, str]:
    if len(history) < MOMENTUM_MIN_SAMPLES:
        return 0.0, "insufficient_data"

    prices = list(history)
    n = len(prices)
    half = n // 2
    early_avg = sum(prices[:half]) / half
    late_avg = sum(prices[half:]) / (n - half)

    diff = late_avg - early_avg
    score = max(-1.0, min(1.0, diff / 0.10))
    direction = "up" if score > 0.05 else ("down" if score < -0.05 else "flat")
    return score, direction


def _mean_revert_score(mid_price: float) -> tuple[float, str]:
    dist = mid_price - 0.5
    if abs(mid_price - 0.5) > MEAN_REVERT_EXTREME_THRESHOLD:
        return 0.0, "extreme_price_suppressed"

    score = -dist * 2.0
    score = max(-1.0, min(1.0, score))
    label = "lean_no" if score < -0.1 else ("lean_yes" if score > 0.1 else "neutral")
    return score, label


def _imbalance_score(imbalance: float) -> tuple[float, str]:
    score = max(-1.0, min(1.0, imbalance))
    label = "yes_pressure" if score > 0.2 else ("no_pressure" if score < -0.2 else "balanced")
    return score, label


def _spread_quality_score(spread_yes: float | None) -> float:
    if spread_yes is None:
        return 0.0
    max_spread = float(os.getenv("MAX_SPREAD", "0.04"))
    return max(0.0, 1.0 - spread_yes / max_spread)


_SUPPRESSION_REASONS = {
    "late_game_too_volatile", "spread_too_early", "total_too_early",
    "spread_line_missing", "total_line_missing",
    "late_inning_too_volatile",
}


def generate_signal(
    market: Market,
    ob: OBSnapshot,
    extract_teams_fn: Callable[[str], tuple[str, str]],
    get_game_state_fn: Callable[[str, str], Any],
    game_signal_fn: Callable[[Market, Any, OBSnapshot], tuple[float, str, dict]],
) -> Signal:
    """
    Generate a directional signal for any sport binary market.
    extract_teams_fn, get_game_state_fn, game_signal_fn are injected by sport adapter.
    """
    reasons: list[str] = []
    components: dict[str, Any] = {}

    if not ob.micro_ok:
        return Signal(
            side="NONE", confidence=0.0,
            fair_value_estimate=0.5,
            components={}, reasons=[f"micro_not_ok:{ob.micro_reason}"],
        )

    if market.market_type == "other":
        return Signal(
            side="NONE", confidence=0.0,
            fair_value_estimate=0.5,
            components={}, reasons=["market_type_other"],
        )

    mid_yes = ((ob.bid_yes or 0) + (ob.ask_yes or 0)) / 2.0
    if mid_yes <= 0:
        mid_yes = 0.5

    # OB microstructure components
    history = _update_price_history(market.market_id, ob)
    mom_score, mom_label = _momentum_score(history)
    mr_score, mr_label = _mean_revert_score(mid_yes)
    imb_score, imb_label = _imbalance_score(ob.imbalance)
    spread_quality = _spread_quality_score(ob.spread_yes)

    # Suppress mean reversion at extreme prices — strong fundamentals are not mean reverting
    if mid_yes >= 0.70 or mid_yes <= 0.30:
        mr_score = 0.0
        mr_label = "suppressed_extreme_price"

    # Only apply momentum when spread is tight (real signal, not noise)
    _tight_spread_threshold = float(os.getenv("MAX_SPREAD", "0.04")) * 0.75
    if ob.spread_yes is None or ob.spread_yes > _tight_spread_threshold:
        mom_score = 0.0
        mom_label = "suppressed_wide_spread"

    components["momentum"] = {"score": round(mom_score, 4), "label": mom_label}
    components["mean_revert"] = {"score": round(mr_score, 4), "label": mr_label}
    components["imbalance"] = {"score": round(imb_score, 4), "label": imb_label}
    components["spread_quality"] = round(spread_quality, 4)

    # Extract teams and fetch game state
    home, away = extract_teams_fn(market.question)
    if not home or not away:
        return Signal(
            side="NONE", confidence=0.0,
            fair_value_estimate=mid_yes,
            components=components, reasons=["no_teams_parsed"],
        )

    try:
        gs = get_game_state_fn(home, away)
    except Exception as e:
        logger.debug("game_state fetch failed: %s", e)
        return Signal(
            side="NONE", confidence=0.0,
            fair_value_estimate=mid_yes,
            components=components, reasons=["espn_unavailable"],
        )

    # Only trade during live games
    if gs.status not in LIVE_STATUSES:
        # Market went offline — reset warmup so next live transition re-gates
        _MARKET_FIRST_LIVE.pop(market.market_id, None)
        return Signal(
            side="NONE", confidence=0.0,
            fair_value_estimate=mid_yes,
            components=components, reasons=[f"not_live:{gs.status}"],
        )

    # A3 — live warmup: block entries for LIVE_WARMUP_SECONDS after first going live
    if LIVE_WARMUP_SECONDS > 0:
        if market.market_id not in _MARKET_FIRST_LIVE:
            _MARKET_FIRST_LIVE[market.market_id] = time.time()
        elapsed = time.time() - _MARKET_FIRST_LIVE[market.market_id]
        if elapsed < LIVE_WARMUP_SECONDS:
            return Signal(
                side="NONE", confidence=0.0,
                fair_value_estimate=mid_yes,
                components=components,
                reasons=[f"live_warmup:{elapsed:.0f}s<{LIVE_WARMUP_SECONDS}s"],
            )

    # Sport-specific game context signal
    game_score, game_reason, game_ctx = game_signal_fn(market, gs, ob)

    components["game_context"] = {"score": round(game_score, 4), "reason": game_reason, **game_ctx}

    if game_reason in _SUPPRESSION_REASONS:
        return Signal(
            side="NONE", confidence=0.0,
            fair_value_estimate=mid_yes,
            components=components,
            reasons=[game_reason],
        )

    # Game weight by market type
    if market.market_type == "spread":
        w_game = W_GAME_SPREAD
    elif market.market_type == "total":
        w_game = W_GAME_TOTAL
    else:
        w_game = W_GAME_MONEYLINE

    # Composite signal: normalize OB weights to fill (1 - w_game)
    ob_weight = 1.0 - w_game
    ob_sum = W_MOMENTUM + W_MEAN_REVERT + W_IMBALANCE
    w_mom = W_MOMENTUM / ob_sum * ob_weight
    w_mr = W_MEAN_REVERT / ob_sum * ob_weight
    w_imb = W_IMBALANCE / ob_sum * ob_weight

    raw_score = (
        w_mom * mom_score
        + w_mr * mr_score
        + w_imb * imb_score
        + w_game * game_score
    )

    confidence_raw = abs(raw_score) * (0.7 + 0.3 * spread_quality)
    confidence = max(0.0, min(1.0, confidence_raw))

    fair_value = max(0.01, min(0.99, mid_yes + raw_score * 0.05))

    if raw_score > 0.08:
        side = "BUY_YES"
        reasons.append(f"lean_yes raw={raw_score:.3f}")
    elif raw_score < -0.08:
        side = "BUY_NO"
        reasons.append(f"lean_no raw={raw_score:.3f}")
    else:
        side = "NONE"
        reasons.append(f"signal_flat raw={raw_score:.3f}")

    if side != "NONE" and confidence < MIN_CONFIDENCE:
        reasons.append(f"confidence_too_low {confidence:.3f}<{MIN_CONFIDENCE}")
        side = "NONE"

    components["raw_score"] = round(raw_score, 4)
    components["weights"] = {
        "momentum": round(w_mom, 4), "mean_revert": round(w_mr, 4),
        "imbalance": round(w_imb, 4), "game": w_game,
    }

    return Signal(
        side=side,
        confidence=round(confidence, 4),
        fair_value_estimate=round(fair_value, 4),
        components=components,
        reasons=reasons,
    )
