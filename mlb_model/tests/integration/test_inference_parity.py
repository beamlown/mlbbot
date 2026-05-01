"""
Verify that adding phase-1 features to inference doesn't break the existing
22-column path: same snapshot + neutral phase-1 extras should give a 30-column
feature vector, with derived columns (sp_quality_diff, park_run_factor_x_late)
correctly zero when inputs are neutral.
"""
import numpy as np
import pytest
from types import SimpleNamespace
from sports.mlb import winprob_inference as wi


def test_neutral_extras_produces_30_col_vector():
    wi._feature_columns = [
        "pregame_logit","score_diff","abs_score_diff","tied","inning","half","outs",
        "game_progress","late_game","base_state","base_state_value",
        "score_diff_x_late","base_value_x_late","tied_x_late",
        "home_pitch_count_norm","home_tto","home_is_bullpen",
        "away_pitch_count_norm","away_tto","away_is_bullpen",
        "elo_diff_norm","late_tie_bottom",
        "home_sp_quality","away_sp_quality","home_sp_recent_form","away_sp_recent_form",
        "sp_quality_diff","park_run_factor","park_run_factor_x_late","pregame_prior_source",
    ]
    snap = SimpleNamespace(
        score_diff=0, inning=5, inning_half=0, outs=1, outs_elapsed=24,
        base_state=0, home_pitch_count=70, away_pitch_count=72,
        home_tto=2.0, away_tto=2.0, home_is_bullpen=False, away_is_bullpen=False,
    )
    extras_neutral = {"home_sp_quality": 100, "away_sp_quality": 100,
                      "home_sp_recent_form": 0, "away_sp_recent_form": 0,
                      "park_run_factor": 1.0, "pregame_prior_source": 1,
                      "home_sp_imputed": False, "away_sp_imputed": False}
    X, feat, q = wi._build_feature_vector(snap, 0.55, extras_neutral)
    assert X.shape == (1, 30)
    assert feat["sp_quality_diff"] == 0
    assert feat["park_run_factor_x_late"] == 0.0
