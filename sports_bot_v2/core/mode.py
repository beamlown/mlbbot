"""
core/mode.py — Adaptive mode controller: conservative / neutral / aggressive
v6-style dwell/hysteresis to prevent rapid mode flips. Sport-agnostic.
"""
from __future__ import annotations

import logging
import os
import time

from core.types import ModeCtx

logger = logging.getLogger("core.mode")

MODE_DWELL_TRADES = int(os.getenv("MODE_DWELL_TRADES", "10"))
SCORE_UPSHIFT = float(os.getenv("ADAPTIVE_UPSHIFT_SCORE", "0.65"))
SCORE_DOWNSHIFT = float(os.getenv("ADAPTIVE_DOWNSHIFT_SCORE", "0.35"))

_MODE_PROFILES: dict[str, dict[str, float]] = {
    "conservative": {
        "min_confidence": 1.10,   # was 1.20 — cap penalty to prevent deadlock
        "max_spread": 0.85,
        "min_depth_usd": 1.25,
        "max_concurrent": 1.0,
    },
    "neutral": {
        "min_confidence": 1.00,
        "max_spread": 1.00,
        "min_depth_usd": 1.00,
        "max_concurrent": float(os.getenv("MAX_CONCURRENT_TRADES", "3")),
    },
    "aggressive": {
        "min_confidence": 0.90,
        "max_spread": 1.10,
        "min_depth_usd": 0.90,
        "max_concurrent": 5.0,
    },
}

_current_mode: str = "neutral"
_dwell_since_switch: int = 0
_last_switch_reason: str = "init"
_last_score: float = 0.5
_last_trade_time: float = 0.0   # updated by record_closed_trade()


def _compute_score(stats: dict) -> float:
    n = stats.get("n", 0)
    if n < 3:
        return 0.5

    win_rate = stats.get("win_rate", 50.0) / 100.0
    expectancy = float(stats.get("expectancy", 0.0))
    avg_win = float(stats.get("avg_win", 0.0))

    wr_score = win_rate

    if avg_win > 0:
        exp_score = max(-1.0, min(1.0, expectancy / avg_win))
    else:
        exp_score = -0.5 if expectancy < 0 else 0.0
    exp_score_norm = (exp_score + 1.0) / 2.0

    loss_rate = stats.get("losses", 0) / max(n, 1)
    streak_score = 1.0 - min(1.0, loss_rate * 1.5)

    score = 0.40 * wr_score + 0.40 * exp_score_norm + 0.20 * streak_score
    return round(max(0.0, min(1.0, score)), 4)


_MODE_TIMEOUT_RECOVERY_SECONDS = int(os.getenv("MODE_TIMEOUT_RECOVERY_SEC", "1800"))
_MODE_MIN_SAMPLE_FOR_CONSERVATIVE = int(os.getenv("MODE_MIN_SAMPLE_FOR_CONSERVATIVE", "20"))


def update_mode(rolling_stats_r25: dict) -> ModeCtx:
    global _current_mode, _dwell_since_switch, _last_switch_reason, _last_score

    score = _compute_score(rolling_stats_r25)
    _last_score = score

    # Not enough sample history to justify conservative — pin to neutral
    n_recent = rolling_stats_r25.get("n", 0)
    if n_recent < _MODE_MIN_SAMPLE_FOR_CONSERVATIVE and _current_mode == "conservative":
        _current_mode = "neutral"
        _dwell_since_switch = 0
        _last_switch_reason = f"insufficient_sample n={n_recent}<{_MODE_MIN_SAMPLE_FOR_CONSERVATIVE}"

    new_mode = _current_mode
    switch_reason = ""

    # Time-based recovery: no trades for 30 min in conservative → nudge to neutral
    if (_current_mode == "conservative" and _last_trade_time > 0
            and time.time() - _last_trade_time > _MODE_TIMEOUT_RECOVERY_SECONDS):
        new_mode = "neutral"
        switch_reason = "timeout_recovery"

    elif score < SCORE_DOWNSHIFT and _current_mode != "conservative":
        if _dwell_since_switch >= MODE_DWELL_TRADES:
            if _current_mode == "aggressive":
                new_mode = "neutral"
                switch_reason = f"downshift aggressive→neutral score={score:.3f}"
            else:
                new_mode = "conservative"
                switch_reason = f"downshift neutral→conservative score={score:.3f}"
        else:
            switch_reason = f"downshift_pending dwell={_dwell_since_switch}/{MODE_DWELL_TRADES}"

    elif score > SCORE_UPSHIFT and _current_mode != "aggressive":
        if _dwell_since_switch >= MODE_DWELL_TRADES:
            if _current_mode == "conservative":
                new_mode = "neutral"
                switch_reason = f"upshift conservative→neutral score={score:.3f}"
            else:
                new_mode = "aggressive"
                switch_reason = f"upshift neutral→aggressive score={score:.3f}"
        else:
            switch_reason = f"upshift_pending dwell={_dwell_since_switch}/{MODE_DWELL_TRADES}"

    if new_mode != _current_mode:
        logger.info("Mode switch: %s → %s (%s)", _current_mode, new_mode, switch_reason)
        _current_mode = new_mode
        _dwell_since_switch = 0
        _last_switch_reason = switch_reason
    else:
        _last_switch_reason = switch_reason or f"holding_{_current_mode}"

    mults = dict(_MODE_PROFILES[_current_mode])

    return ModeCtx(
        mode=_current_mode,
        score=score,
        dwell_trades=_dwell_since_switch,
        profile_multipliers=mults,
        switch_reason=_last_switch_reason,
    )


def record_closed_trade() -> None:
    global _dwell_since_switch, _last_trade_time
    _dwell_since_switch += 1
    _last_trade_time = time.time()


def get_mode_ctx() -> ModeCtx:
    return ModeCtx(
        mode=_current_mode,
        score=_last_score,
        dwell_trades=_dwell_since_switch,
        profile_multipliers=dict(_MODE_PROFILES[_current_mode]),
        switch_reason=_last_switch_reason,
    )
