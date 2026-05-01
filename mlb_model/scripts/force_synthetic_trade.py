"""
scripts/force_synthetic_trade.py — Diagnostic: force a synthetic live game through
the model + edge gate, iterating scenarios until an actionable trade is produced.

Proves:
  1. Model artifacts load
  2. 36-feature vector builds cleanly
  3. Calibrator produces p_home
  4. Edge calc vs synthetic market price
  5. Action = BUY_YES / BUY_NO given enough edge

Does NOT hit ESPN / MLB Stats / Polymarket — fully synthetic.

Usage:
    python scripts/force_synthetic_trade.py
"""
from __future__ import annotations
import sys
from pathlib import Path
from types import SimpleNamespace

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sports.mlb.winprob_inference import load_artifacts, infer_for_team, is_loaded


def synthetic_snap(*, inning, inning_half, outs, score_diff, base_state=0,
                   home_pc=70, away_pc=70, home_bullpen=False, away_bullpen=False):
    """Build a minimal SimpleNamespace GameStateSnapshot-compatible object."""
    outs_el = (inning - 1) * 6 + inning_half * 3 + outs
    return SimpleNamespace(
        game_id="SYNTH1", home_team="LAA", away_team="SDP", date="2026-04-20",
        home_score=max(0, score_diff), away_score=max(0, -score_diff),
        score_diff=score_diff,
        inning=inning, inning_half=inning_half, outs=outs,
        base_state=base_state,
        status="LATE_GAME" if inning >= 7 else "MID_GAME",
        game_progress=min(1.0, outs_el / 54.0),
        outs_elapsed=outs_el,
        home_pitcher_id=100001, away_pitcher_id=200001,
        home_pitch_count=home_pc, away_pitch_count=away_pc,
        home_is_bullpen=home_bullpen, away_is_bullpen=away_bullpen,
        home_tto=min(3.0, home_pc / 27.0 + 1.0),
        away_tto=min(3.0, away_pc / 27.0 + 1.0),
        is_live=True, fetched_at=0.0, espn_fetched_at="",
    )


def main() -> int:
    print("=== force_synthetic_trade diagnostic ===\n")

    # 1. Load artifacts
    load_artifacts()
    if not is_loaded():
        print("FAIL: artifacts did not load")
        return 1
    print("artifacts loaded OK (36-feature model)\n")

    # 2. Sweep scenarios — all plausible LAA-leading late-game spots
    scenarios = [
        # (label, snap kwargs, pregame_home_prob, market_yes_cost, market_no_cost)
        ("Tied 7th, bases empty",
         dict(inning=7, inning_half=0, outs=1, score_diff=0, base_state=0),
         0.55, 0.50, 0.52),
        ("Home up 1 in bot 8, 1 out, bases loaded",
         dict(inning=8, inning_half=1, outs=1, score_diff=1, base_state=7),
         0.55, 0.70, 0.35),
        ("Home up 3 in top 9, 0 out, bullpen in",
         dict(inning=9, inning_half=0, outs=0, score_diff=3, base_state=0,
              home_bullpen=True, home_pc=15),
         0.55, 0.85, 0.18),
        ("Home down 2 in bot 9, 1 out, runner on 2nd",
         dict(inning=9, inning_half=1, outs=1, score_diff=-2, base_state=2),
         0.55, 0.20, 0.82),
        ("Extras 10th tied, ghost runner, 0 out",
         dict(inning=10, inning_half=0, outs=0, score_diff=0, base_state=2),
         0.55, 0.50, 0.52),
    ]

    # Phase-1/2/3/4 extras — mostly neutral, one with strong bullpen edge
    neutral_p1 = {"home_sp_quality": 95, "away_sp_quality": 100,
                  "home_sp_recent_form": 0.5, "away_sp_recent_form": -0.2,
                  "park_run_factor": 1.0, "pregame_prior_source": 1,
                  "home_sp_imputed": False, "away_sp_imputed": False}
    neutral_p2 = {"lineup_avg_xwoba": 100, "current_batter_imputed": False}
    neutral_p3 = {"home_reliever_quality": 95, "away_reliever_quality": 105,
                  "home_bullpen_avg_quality": 92, "away_bullpen_avg_quality": 105,
                  "leverage_index": 2.5}
    neutral_p4 = {"wind_out_mph": 0, "temp_f": 72, "is_roof_closed": 0,
                  "ghost_runner_on_2nd": 0}

    MIN_EDGE = 0.05
    actionable_found = []

    for label, kwargs, prior, yes_cost, no_cost in scenarios:
        snap = synthetic_snap(**kwargs)
        p_home_tracked, result = infer_for_team(
            snap, tracked_team="LAA", pregame_win_prob_home=prior,
            phase1_extras=neutral_p1, phase2_extras=neutral_p2,
            phase3_extras=neutral_p3, phase4_extras=neutral_p4,
        )
        p_tracked = p_home_tracked
        edge_yes = p_tracked - yes_cost
        edge_no = (1 - p_tracked) - no_cost
        action = "NO_TRADE"
        if edge_yes > edge_no and edge_yes >= MIN_EDGE:
            action = "BUY_YES"
        elif edge_no > edge_yes and edge_no >= MIN_EDGE:
            action = "BUY_NO"

        print(f"--- {label}")
        print(f"    p_home_calibrated = {result.p_home:.4f}   (raw {result.raw_prob:.4f})")
        print(f"    yes_cost={yes_cost:.3f}  no_cost={no_cost:.3f}  "
              f"edge_yes={edge_yes:+.4f}  edge_no={edge_no:+.4f}")
        print(f"    data_quality={result.data_quality:.3f}")
        print(f"    ACTION: {action}")
        if action != "NO_TRADE":
            actionable_found.append((label, action, max(edge_yes, edge_no)))
        print()

    print("=== SUMMARY ===")
    if actionable_found:
        print(f"{len(actionable_found)} actionable trades produced from {len(scenarios)} scenarios:")
        for label, action, edge in actionable_found:
            print(f"  [{action}] edge={edge:+.4f}  |  {label}")
        return 0
    else:
        print("NO actionable trades across these scenarios — model + edge gates functional but")
        print("all synthetic markets happened to be priced at the calibrated probability.")
        print("Re-run with more aggressive market-mispricing scenarios if you want to force one.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
