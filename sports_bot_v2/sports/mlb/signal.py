"""
sports/mlb/signal.py — MLB game context signal generation
Baseball-specific: pitcher quality, inning proximity, bullpen fatigue, scoring runs.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

from core.types import Market, OBSnapshot

logger = logging.getLogger("sports.mlb.signal")

_SPREAD_DIR_RE = re.compile(r"-spread-(home|away)-(\d+(?:pt\d+)?)", re.IGNORECASE)

# Thresholds
SCORING_RUN_THRESHOLD = int(os.getenv("SCORING_RUN_THRESHOLD_MLB", "3"))
LATE_INNING_BLOCK = int(os.getenv("LATE_INNING_BLOCK", "7"))
PITCHER_FATIGUE_PITCHES = int(os.getenv("PITCHER_FATIGUE_PITCH_COUNT", "90"))
SPREAD_MIN_OUTS = int(os.getenv("SPREAD_MIN_OUTS_MLB", "9"))    # ~3 innings
TOTAL_MIN_OUTS = int(os.getenv("TOTAL_MIN_OUTS_MLB", "9"))
SPREAD_COVER_NORM = float(os.getenv("SPREAD_COVER_NORM_MLB", "3.0"))
TOTAL_NORM = float(os.getenv("TOTAL_NORM_MLB", "2.0"))


def _outs_elapsed(gs) -> int:
    """Total outs elapsed in the game (approx). 3 outs per half-inning."""
    if gs.inning <= 0:
        return 0
    completed_half_innings = (gs.inning - 1) * 2
    if gs.inning_half == "bottom":
        completed_half_innings += 1
    return completed_half_innings * 3 + gs.outs


def _total_outs_in_game(gs) -> int:
    """Total outs in a standard 9-inning game = 54."""
    if gs.inning > 9:
        return 54 + (gs.inning - 9) * 6
    return 54


def normalize_tokens(name: str) -> list[str]:
    return [w.lower() for w in name.split() if len(w) > 2]


def _signal_moneyline(market: Market, gs, ob: OBSnapshot) -> tuple[float, str, dict[str, Any]]:
    """
    MLB moneyline signal.
    Positive = lean YES (home wins), negative = lean NO.
    """
    score = 0.0
    reasons: list[str] = []
    ctx: dict[str, Any] = {
        "status": gs.status,
        "home": gs.home_team,
        "away": gs.away_team,
        "score": f"{gs.home_score}-{gs.away_score}",
        "inning": gs.inning,
        "inning_half": gs.inning_half,
        "outs": gs.outs,
    }

    margin = gs.home_score - gs.away_score

    # --- Lead score: baseball is tighter than basketball ---
    lead_score = max(-0.4, min(0.4, margin / 4.0))
    score = lead_score

    # --- Inning proximity: confidence builds as game ends ---
    # After inning 7, fewer at-bats remain → lead becomes more durable
    if gs.inning >= 7 and margin != 0:
        inning_weight = min(0.15, (gs.inning - 6) * 0.05)
        direction = 1 if margin > 0 else -1
        score += inning_weight * direction
        reasons.append(f"late_inning_boost_i{gs.inning}")
        ctx["inning_proximity"] = inning_weight

    # --- Pitcher quality delta (pre-game / early innings) ---
    if gs.inning <= 4 and gs.home_pitcher_era5 > 0 and gs.away_pitcher_era5 > 0:
        era_diff = gs.away_pitcher_era5 - gs.home_pitcher_era5   # positive = home pitcher better
        era_signal = max(-0.20, min(0.20, era_diff / 2.0))
        score += era_signal
        if abs(era_signal) > 0.03:
            reasons.append(f"pitcher_era_delta_{era_diff:+.2f}")
        ctx["era_delta"] = round(era_diff, 2)

    # --- Pitcher fatigue: approaching or over pitch limit ---
    current_pitcher_pitches = (
        gs.home_pitcher_pitches if gs.inning_half == "bottom" else gs.away_pitcher_pitches
    )
    if current_pitcher_pitches >= PITCHER_FATIGUE_PITCHES:
        # Pitching team about to use bullpen → uncertainty / slight fade for pitching side
        if gs.inning_half == "top":  # away pitcher tired → slight home boost (batting team gains)
            score += 0.06
            reasons.append(f"away_pitcher_fatigue_{current_pitcher_pitches}p")
        else:
            score -= 0.06
            reasons.append(f"home_pitcher_fatigue_{current_pitcher_pitches}p")
        ctx["pitcher_pitches"] = current_pitcher_pitches

    # --- Scoring run: 3+ consecutive runs this half-inning ---
    if gs.scoring_run_pts >= SCORING_RUN_THRESHOLD and gs.scoring_run_team:
        run_favor_home = any(
            tok in gs.scoring_run_team.lower()
            for tok in normalize_tokens(gs.home_team)
        )
        boost = min(0.25, gs.scoring_run_pts * 0.06)
        if run_favor_home:
            score += boost
            reasons.append(f"scoring_run_home_{gs.scoring_run_pts}r")
        else:
            score -= boost
            reasons.append(f"scoring_run_away_{gs.scoring_run_pts}r")
        ctx["scoring_run"] = f"{gs.scoring_run_team} {gs.scoring_run_pts}r"

    # --- Runners on base with outs: scoring threat ---
    if gs.runners_on and gs.outs <= 1 and abs(margin) <= 2:
        batting_is_home = gs.inning_half == "bottom"
        threat_boost = 0.04 if gs.runners_on == "loaded" else 0.02
        score += threat_boost if batting_is_home else -threat_boost
        reasons.append(f"risp_{gs.runners_on}")
        ctx["runners_on"] = gs.runners_on

    # --- Sharp odds component — lazy import, zero overhead when disabled ---
    _W_SHARP = float(os.getenv("SIG_W_SHARP_MONEYLINE", "0.0"))
    if _W_SHARP > 0.0:
        from sports.mlb.sharp_odds import get_sharp_prob
        sharp_prob = get_sharp_prob(gs.home_team, gs.away_team)
        if sharp_prob is not None:
            sharp_edge = sharp_prob - (ob.ask_yes or 0.5)
            _EDGE_SCALE = float(os.getenv("SHARP_EDGE_SCALE", "0.10"))
            _MIN_SHARP_EDGE = float(os.getenv("MIN_SHARP_EDGE", "0.03"))
            sharp_score = max(-1.0, min(1.0, sharp_edge / _EDGE_SCALE))
            if abs(sharp_edge) < _MIN_SHARP_EDGE:
                sharp_score = 0.0  # below noise floor — treat as neutral
            contribution = max(-0.30, min(0.30, sharp_score * _W_SHARP))
            score = max(-1.0, min(1.0, score + contribution))
            reasons.append(f"sharp_edge={sharp_edge:+.3f}(score={sharp_score:+.2f})")
            ctx["sharp_prob"] = round(sharp_prob, 4)
            ctx["sharp_edge"] = round(sharp_edge, 4)
            ctx["sharp_score"] = round(sharp_score, 4)

    # --- Late inning close game suppression (like NCAAB final 3 min) ---
    if gs.inning >= LATE_INNING_BLOCK and abs(margin) <= 1:
        ctx["late_game_block"] = True
        return 0.0, "late_inning_too_volatile", ctx

    ctx["reasons"] = reasons
    return max(-1.0, min(1.0, score)), "|".join(reasons) or "game_context_neutral", ctx


def _signal_spread(market: Market, gs, ob: OBSnapshot) -> tuple[float, str, dict[str, Any]]:
    """MLB run line signal."""
    if market.spread_line is None:
        return 0.0, "spread_line_missing", {}

    m = _SPREAD_DIR_RE.search(market.slug.lower())
    home_fav = (m.group(1).lower() == "home") if m else True

    fav_margin = (gs.home_score - gs.away_score) if home_fav else (gs.away_score - gs.home_score)
    cover_margin = fav_margin - market.spread_line

    outs = _outs_elapsed(gs)
    if outs < SPREAD_MIN_OUTS:
        return 0.0, "spread_too_early", {"outs_elapsed": outs}

    score = max(-1.0, min(1.0, cover_margin / SPREAD_COVER_NORM))

    # Run scoring momentum for the favored team
    fav_team = gs.home_team if home_fav else gs.away_team
    if gs.scoring_run_pts >= SCORING_RUN_THRESHOLD and gs.scoring_run_team:
        run_for_fav = any(tok in gs.scoring_run_team.lower()
                          for tok in normalize_tokens(fav_team))
        boost = min(0.20, gs.scoring_run_pts * 0.05)
        score = max(-1.0, min(1.0, score + (boost if run_for_fav else -boost)))

    # Late innings: run line very hard to cover — dampen
    if gs.inning >= 8:
        score *= 0.70

    ctx = {"cover_margin": cover_margin, "fav_margin": fav_margin,
           "spread_line": market.spread_line, "outs_elapsed": outs,
           "inning": gs.inning}
    return score, f"cover_margin={cover_margin:.1f}", ctx


def _signal_total(market: Market, gs, ob: OBSnapshot) -> tuple[float, str, dict[str, Any]]:
    """MLB totals (over/under runs) signal."""
    if market.total_line is None:
        return 0.0, "total_line_missing", {}

    outs = _outs_elapsed(gs)
    if outs < TOTAL_MIN_OUTS:
        return 0.0, "total_too_early", {"outs_elapsed": outs}

    current_total = gs.home_score + gs.away_score
    total_outs = _total_outs_in_game(gs)
    pace_factor = total_outs / max(outs, 1)
    projected = current_total * pace_factor

    deviation = projected - market.total_line
    score = max(-1.0, min(1.0, deviation / TOTAL_NORM))

    # Pitcher matchup quality: both starters have low ERA → lean under early
    if gs.inning <= 3 and gs.home_pitcher_era5 > 0 and gs.away_pitcher_era5 > 0:
        avg_era = (gs.home_pitcher_era5 + gs.away_pitcher_era5) / 2.0
        if avg_era < 3.00:
            score -= 0.08   # elite pitching → under lean
            score = max(-1.0, score)
        elif avg_era > 5.00:
            score += 0.06   # bad pitching → over lean
            score = min(1.0, score)

    # Scoring runs in either direction → over signal
    if gs.scoring_run_pts >= SCORING_RUN_THRESHOLD:
        score += 0.07
        score = min(1.0, score)

    ctx = {"current_total": current_total, "projected": round(projected, 1),
           "total_line": market.total_line, "pace_factor": round(pace_factor, 2),
           "outs_elapsed": outs, "inning": gs.inning}
    return score, f"proj={projected:.1f} line={market.total_line}", ctx


def game_signal(market: Market, gs, ob: OBSnapshot) -> tuple[float, str, dict[str, Any]]:
    """Dispatch to MLB market-type sub-signal. Called by core/signal_base.py."""
    # Blowout filter — applies to all market types
    score_diff = abs(gs.home_score - gs.away_score)
    if gs.status in ("FINAL", "post") or (gs.inning >= 8 and score_diff >= 6):
        return 0.0, "blowout_skip", {
            "status": gs.status, "inning": gs.inning, "score_diff": score_diff
        }

    if market.market_type == "spread":
        return _signal_spread(market, gs, ob)
    elif market.market_type == "total":
        return _signal_total(market, gs, ob)
    else:
        return _signal_moneyline(market, gs, ob)
