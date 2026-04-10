"""
sports/ncaab/signal.py — NCAAB game context signal generation
Ported from march_madness_bot mm_signal.py (game-specific portion).
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

from core.types import Market, OBSnapshot

logger = logging.getLogger("sports.ncaab.signal")

_SPREAD_DIR_RE = re.compile(r"-spread-(home|away)-(\d+(?:pt\d+)?)", re.IGNORECASE)

SCORING_RUN_THRESHOLD = int(os.getenv("SCORING_RUN_THRESHOLD", "8"))
FINAL_MINUTES_BLOCK_SECONDS = int(os.getenv("FINAL_MINUTES_BLOCK_SECONDS", "180"))
SPREAD_MIN_ELAPSED_SEC = float(os.getenv("SPREAD_MIN_ELAPSED_SEC", "300"))
TOTAL_MIN_ELAPSED_SEC = float(os.getenv("TOTAL_MIN_ELAPSED_SEC", "300"))
SPREAD_COVER_NORM = float(os.getenv("SPREAD_COVER_NORM", "7.0"))
TOTAL_NORM = float(os.getenv("TOTAL_NORM", "8.0"))


def normalize_tokens(name: str) -> list[str]:
    return [w.lower() for w in name.split() if len(w) > 2]


def _elapsed_seconds(gs) -> float:
    if gs.status in ("PRE_GAME", "unknown"):
        return 0.0
    clock_secs = 0
    if gs.clock:
        try:
            p = gs.clock.split(":")
            clock_secs = int(p[0]) * 60 + int(p[1])
        except Exception:
            pass
    HALF = 1200
    OT = 300
    if gs.status == "HALFTIME":
        return float(HALF)
    if gs.period == 1:
        return float(HALF - clock_secs)
    if gs.period == 2:
        return float(HALF + (HALF - clock_secs))
    if gs.period > 2:
        return float(2 * HALF + (gs.period - 3) * OT + (OT - clock_secs))
    if gs.status == "FINAL":
        return float(2 * HALF)
    return 0.0


def _total_game_seconds(gs) -> float:
    if gs.period <= 2:
        return 2400.0
    return 2400.0 + (gs.period - 2) * 300.0


def _signal_moneyline(market: Market, gs, ob: OBSnapshot) -> tuple[float, str, dict[str, Any]]:
    score = 0.0
    reasons = []
    ctx: dict[str, Any] = {
        "status": gs.status,
        "home": gs.home_team,
        "away": gs.away_team,
        "score": f"{gs.home_score}-{gs.away_score}",
        "period": gs.period,
        "clock": gs.clock,
    }

    margin = gs.home_score - gs.away_score
    lead_score = max(-0.3, min(0.3, margin / 25.0))
    score = lead_score

    if gs.scoring_run_pts >= SCORING_RUN_THRESHOLD and gs.scoring_run_team:
        run_favor_home = any(
            tok in gs.scoring_run_team.lower()
            for tok in normalize_tokens(gs.home_team)
        )
        boost = min(0.4, gs.scoring_run_pts * 0.025)
        if run_favor_home:
            score += boost
            reasons.append(f"scoring_run_home_{gs.scoring_run_pts}pt")
        else:
            score -= boost
            reasons.append(f"scoring_run_away_{gs.scoring_run_pts}pt")
        ctx["scoring_run"] = f"{gs.scoring_run_team} {gs.scoring_run_pts}pt"

    if gs.halftime_adj != 0.0:
        score += gs.halftime_adj
        reasons.append(f"halftime_adj_{gs.halftime_adj:+.2f}")
        ctx["halftime_adj"] = gs.halftime_adj

    if margin != 0:
        leading_is_home = margin > 0
        leading_fouls = gs.home_fouls if leading_is_home else gs.away_fouls
        if leading_fouls >= 5:
            foul_fade = min(0.10, (leading_fouls - 4) * 0.025)
            score -= foul_fade * (1 if leading_is_home else -1)
            reasons.append(f"foul_trouble_{leading_fouls}")
            ctx["leading_team_fouls"] = leading_fouls

    if gs.in_bonus:
        trailing_is_home = margin < 0
        home_in_bonus = gs.in_bonus in ("home", "both")
        away_in_bonus = gs.in_bonus in ("away", "both")
        if trailing_is_home and home_in_bonus:
            score += 0.03
            reasons.append("home_in_bonus_trailing")
        elif not trailing_is_home and away_in_bonus and margin > 0:
            score -= 0.03
            reasons.append("away_in_bonus_trailing")
        ctx["in_bonus"] = gs.in_bonus

    if gs.is_timeout and abs(margin) <= 12:
        revert = 0.04 * (-1 if margin > 0 else 1)
        score += revert
        reasons.append("timeout_momentum_revert")
        ctx["is_timeout"] = True

    if gs.possession and abs(margin) <= 4:
        poss_home = gs.possession == "home"
        score += 0.015 if poss_home else -0.015
        ctx["possession"] = gs.possession

    if gs.status in ("SECOND_HALF", "OVERTIME"):
        try:
            mins_str, secs_str = gs.clock.split(":")
            secs_left = int(mins_str) * 60 + int(secs_str)
            if secs_left < 120:
                if gs.home_timeouts == 0 and margin > 0:
                    score -= 0.04
                    reasons.append("home_no_timeouts_final2")
                elif gs.away_timeouts == 0 and margin < 0:
                    score += 0.04
                    reasons.append("away_no_timeouts_final2")
        except Exception:
            pass

    if gs.status in ("SECOND_HALF", "OVERTIME"):
        try:
            mins_str, secs_str = gs.clock.split(":")
            secs_left = int(mins_str) * 60 + int(secs_str)
            margin_abs = abs(gs.home_score - gs.away_score)
            if secs_left < FINAL_MINUTES_BLOCK_SECONDS and margin_abs <= 6:
                ctx["late_game_block"] = True
                return 0.0, "late_game_too_volatile", ctx
        except Exception:
            pass

    ctx["reasons"] = reasons
    return max(-1.0, min(1.0, score)), "|".join(reasons) or "game_context_neutral", ctx


def _signal_spread(market: Market, gs, ob: OBSnapshot) -> tuple[float, str, dict[str, Any]]:
    if market.spread_line is None:
        return 0.0, "spread_line_missing", {}

    m = _SPREAD_DIR_RE.search(market.slug.lower())
    home_fav = (m.group(1).lower() == "home") if m else True

    fav_margin = (gs.home_score - gs.away_score) if home_fav else (gs.away_score - gs.home_score)
    cover_margin = fav_margin - market.spread_line

    elapsed = _elapsed_seconds(gs)
    if elapsed < SPREAD_MIN_ELAPSED_SEC:
        return 0.0, "spread_too_early", {"elapsed": elapsed}

    score = max(-1.0, min(1.0, cover_margin / SPREAD_COVER_NORM))

    fav_team = gs.home_team if home_fav else gs.away_team
    if gs.scoring_run_pts >= SCORING_RUN_THRESHOLD and gs.scoring_run_team:
        run_for_fav = any(tok in gs.scoring_run_team.lower()
                          for tok in normalize_tokens(fav_team))
        boost = min(0.3, gs.scoring_run_pts * 0.025)
        score = max(-1.0, min(1.0, score + (boost if run_for_fav else -boost)))

    fav_fouls = gs.home_fouls if home_fav else gs.away_fouls
    if fav_fouls >= 5:
        foul_fade = min(0.08, (fav_fouls - 4) * 0.02)
        score = max(-1.0, min(1.0, score - foul_fade))

    if gs.is_timeout and abs(cover_margin) <= 5:
        score *= 0.85

    ctx = {"cover_margin": cover_margin, "fav_margin": fav_margin,
           "spread_line": market.spread_line, "elapsed_sec": elapsed,
           "fav_fouls": fav_fouls, "is_timeout": gs.is_timeout}
    return score, f"cover_margin={cover_margin:.1f}", ctx


def _signal_total(market: Market, gs, ob: OBSnapshot) -> tuple[float, str, dict[str, Any]]:
    if market.total_line is None:
        return 0.0, "total_line_missing", {}

    elapsed = _elapsed_seconds(gs)
    if elapsed < TOTAL_MIN_ELAPSED_SEC:
        return 0.0, "total_too_early", {"elapsed": elapsed}

    current_total = gs.home_score + gs.away_score
    total_secs = _total_game_seconds(gs)
    pace_factor = total_secs / elapsed
    projected = current_total * pace_factor

    if gs.status == "HALFTIME":
        pace_factor *= 0.85
        projected = current_total * pace_factor

    deviation = projected - market.total_line
    score = max(-1.0, min(1.0, deviation / TOTAL_NORM))

    ctx = {"current_total": current_total, "projected": round(projected, 1),
           "total_line": market.total_line, "pace_factor": round(pace_factor, 2),
           "elapsed_sec": elapsed}
    return score, f"proj={projected:.1f} line={market.total_line}", ctx


def game_signal(market: Market, gs, ob: OBSnapshot) -> tuple[float, str, dict[str, Any]]:
    """Dispatch to NCAAB market-type sub-signal. Called by core/signal_base.py."""
    if market.market_type == "spread":
        return _signal_spread(market, gs, ob)
    elif market.market_type == "total":
        return _signal_total(market, gs, ob)
    else:
        return _signal_moneyline(market, gs, ob)
