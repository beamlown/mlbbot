"""
core/execution_guard.py — Market quality gates for recommendation filtering

These are execution gates, NOT prediction gates. They check whether
the operational conditions are right to act on a recommendation —
not whether the model prediction is correct.

Gates (per spec):
  1. Market type is moneyline
  2. Game is confirmed live (not from price inference — from ESPN registry)
  3. Game-state age <= GAME_STATE_MAX_AGE_SEC
  4. Book age <= BOOK_MAX_AGE_SEC
  5. Live warmup window expired (LIVE_WARMUP_SECONDS after game goes live)
  6. No cooldown active for this market
  7. Near-resolution check (market price >= NEAR_RESOLUTION_PRICE)
  8. Thin-side depth >= MIN_TOUCH_DEPTH_USD
  9. Spread <= MAX_SPREAD
  10. Edge >= MIN_EDGE_THRESHOLD

Public API:
    check_all_gates(rec, market_state, game_state, cooldowns, live_since) -> (bool, list[str])
    check_size_tier(edge) -> (str, float)
"""
from __future__ import annotations

import logging
import os
import time

logger = logging.getLogger(__name__)

# Thresholds (all overridable via env)
MIN_EDGE_THRESHOLD = float(os.getenv("MIN_EDGE_THRESHOLD", "0.05"))
STRONG_EDGE_THRESHOLD = float(os.getenv("STRONG_EDGE_THRESHOLD", "0.08"))
MAX_SPREAD = float(os.getenv("MAX_SPREAD", "0.035"))
MIN_TOUCH_DEPTH_USD = float(os.getenv("MIN_TOUCH_DEPTH_USD", "200"))
NEAR_RESOLUTION_PRICE = float(os.getenv("NEAR_RESOLUTION_PRICE", "0.92"))
LIVE_WARMUP_SECONDS = float(os.getenv("LIVE_WARMUP_SECONDS", "90"))
GAME_STATE_MAX_AGE_SEC = float(os.getenv("GAME_STATE_MAX_AGE_SEC", "15"))
BOOK_MAX_AGE_SEC = float(os.getenv("BOOK_MAX_AGE_SEC", "5"))
MIN_DATA_QUALITY = float(os.getenv("MIN_DATA_QUALITY", "0.70"))


def check_all_gates(
    action: str,                    # "BUY_YES" | "BUY_NO"
    edge: float,                    # edge_yes or edge_no depending on action
    market_type: str,               # "moneyline" | "spread" | "total" | "other"
    game_is_live: bool,             # from live_game_registry, NOT from price
    game_state_age_sec: float,
    book_age_sec: float,
    live_since_sec: float,          # seconds since this game went live
    cooldown_active: bool,
    ask_tracked: float | None,      # ask on the tracked side
    spread: float | None,
    depth_usd: float,               # thin-side depth
    data_quality: float,
    near_resolution: bool = False,  # True if YES or NO bid >= NEAR_RESOLUTION_PRICE
) -> tuple[bool, list[str]]:
    """
    Run all execution gates. Returns (all_ok, reasons_blocked).
    Fails fast on first block.
    """
    # G1 — market type
    if market_type != "moneyline":
        return False, [f"not_moneyline:{market_type}"]

    # G2 — game must be live per external source (not price inference)
    if not game_is_live:
        return False, ["game_not_live"]

    # G3 — game state freshness
    if game_state_age_sec > GAME_STATE_MAX_AGE_SEC:
        return False, [f"stale_game_state:{game_state_age_sec:.1f}s>{GAME_STATE_MAX_AGE_SEC}s"]

    # G4 — book freshness
    if book_age_sec > BOOK_MAX_AGE_SEC:
        return False, [f"stale_book:{book_age_sec:.1f}s>{BOOK_MAX_AGE_SEC}s"]

    # G5 — live warmup
    if live_since_sec < LIVE_WARMUP_SECONDS:
        return False, [f"live_warmup:{live_since_sec:.0f}s<{LIVE_WARMUP_SECONDS}s"]

    # G6 — cooldown
    if cooldown_active:
        return False, ["cooldown_active"]

    # G7 — near resolution
    if near_resolution:
        return False, ["near_resolution"]

    if ask_tracked is not None and ask_tracked >= NEAR_RESOLUTION_PRICE:
        return False, [f"ask_too_high:{ask_tracked:.4f}>={NEAR_RESOLUTION_PRICE}"]

    # G8 — depth
    if depth_usd < MIN_TOUCH_DEPTH_USD:
        return False, [f"depth_too_low:{depth_usd:.1f}<{MIN_TOUCH_DEPTH_USD}"]

    # G9 — spread
    if spread is not None and spread > MAX_SPREAD:
        return False, [f"spread_too_wide:{spread:.4f}>{MAX_SPREAD}"]

    # G10 — data quality
    if data_quality < MIN_DATA_QUALITY:
        return False, [f"data_quality_low:{data_quality:.3f}<{MIN_DATA_QUALITY}"]

    # G11 — edge threshold
    if edge < MIN_EDGE_THRESHOLD:
        return False, [f"edge_too_small:{edge:.4f}<{MIN_EDGE_THRESHOLD}"]

    return True, []


def check_size_tier(edge: float) -> tuple[str, float]:
    """
    Return (tier, size_mult) based on edge magnitude.
    Returns:
        ("strong", 1.5)  if edge >= STRONG_EDGE_THRESHOLD
        ("normal", 1.0)  if edge >= MIN_EDGE_THRESHOLD
        ("none",   0.0)  otherwise
    """
    if edge >= STRONG_EDGE_THRESHOLD:
        return "strong", 1.5
    elif edge >= MIN_EDGE_THRESHOLD:
        return "normal", 1.0
    else:
        return "none", 0.0


def compute_confidence(edge: float, data_quality: float, spread: float | None) -> float:
    """
    Compute a normalized 0-1 confidence score from edge + quality + spread.
    This is informational — execution is gated on the binary gates above.
    """
    spread_quality = 1.0 - (spread or 0.0) / MAX_SPREAD if spread is not None else 0.8
    spread_quality = max(0.0, min(1.0, spread_quality))

    # Edge contribution: 0.05 edge → 0.5 base, scaling to 1.0 at 0.15+
    edge_score = min(1.0, max(0.0, (edge - MIN_EDGE_THRESHOLD) / 0.10 + 0.5))

    confidence = edge_score * data_quality * spread_quality
    return round(confidence, 4)
