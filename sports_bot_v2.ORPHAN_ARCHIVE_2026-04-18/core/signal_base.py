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
