from datetime import date
import numpy as np
import pytest
from sports.mlb.winprob_inference import _build_feature_vector, _PHASE1_FEATURE_NAMES
from types import SimpleNamespace
from sports.mlb import winprob_inference as wi


_FULL_30_COLS = [
    "pregame_logit","score_diff","abs_score_diff","tied","inning","half","outs",
    "game_progress","late_game","base_state","base_state_value",
    "score_diff_x_late","base_value_x_late","tied_x_late",
    "home_pitch_count_norm","home_tto","home_is_bullpen",
    "away_pitch_count_norm","away_tto","away_is_bullpen",
    "elo_diff_norm","late_tie_bottom",
    "home_sp_quality","away_sp_quality","home_sp_recent_form","away_sp_recent_form",
    "sp_quality_diff","park_run_factor","park_run_factor_x_late","pregame_prior_source",
]


@pytest.fixture(autouse=True)
def stub_feature_columns():
    saved = wi._feature_columns
    wi._feature_columns = list(_FULL_30_COLS)
    yield
    wi._feature_columns = saved


def _snap(**kw):
    defaults = dict(
        score_diff=0, inning=1, inning_half=0, outs=0, outs_elapsed=0,
        base_state=0, home_pitch_count=0, away_pitch_count=0,
        home_tto=1.0, away_tto=1.0, home_is_bullpen=False, away_is_bullpen=False,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def test_phase1_feature_names_count():
    assert len(_PHASE1_FEATURE_NAMES) == 8


def test_build_vector_has_all_phase1_keys():
    extras = {
        "home_sp_quality": 95.0, "away_sp_quality": 105.0,
        "home_sp_recent_form": 0.5, "away_sp_recent_form": -0.2,
        "park_run_factor": 1.05, "pregame_prior_source": 0,
        "home_sp_imputed": False, "away_sp_imputed": False,
    }
    X, feat, q = _build_feature_vector(_snap(), pregame_win_prob=0.55, phase1_extras=extras)
    assert X.shape == (1, 30)
    for k in _PHASE1_FEATURE_NAMES:
        assert k in feat


def test_default_pregame_source_lowers_quality_more():
    snap = _snap(home_pitch_count=10, away_pitch_count=10)
    extras_default = {"home_sp_quality": 100, "away_sp_quality": 100,
                      "home_sp_recent_form": 0, "away_sp_recent_form": 0,
                      "park_run_factor": 1.0, "pregame_prior_source": 2,
                      "home_sp_imputed": False, "away_sp_imputed": False}
    extras_sharp = {**extras_default, "pregame_prior_source": 0}
    _, _, q_default = _build_feature_vector(snap, 0.55, phase1_extras=extras_default)
    _, _, q_sharp = _build_feature_vector(snap, 0.55, phase1_extras=extras_sharp)
    # sharp source = 0 penalty; default source = 0.10 penalty
    assert q_sharp - q_default >= 0.10 - 1e-6


def test_phase2_feature_names_count():
    from sports.mlb.winprob_inference import _PHASE2_FEATURE_NAMES
    assert len(_PHASE2_FEATURE_NAMES) == 5


def test_build_vector_with_phase2_extras():
    from sports.mlb import winprob_inference as wi
    wi._feature_columns = [
        "pregame_logit","score_diff","abs_score_diff","tied","inning","half","outs",
        "game_progress","late_game","base_state","base_state_value",
        "score_diff_x_late","base_value_x_late","tied_x_late",
        "home_pitch_count_norm","home_tto","home_is_bullpen",
        "away_pitch_count_norm","away_tto","away_is_bullpen",
        "elo_diff_norm","late_tie_bottom",
        "home_sp_quality","away_sp_quality","home_sp_recent_form","away_sp_recent_form",
        "sp_quality_diff","park_run_factor","park_run_factor_x_late","pregame_prior_source",
        "current_batter_xwoba","next3_avg_xwoba","lineup_avg_xwoba",
        "current_batter_platoon_advantage","current_batter_xwoba_x_late",
    ]
    snap = SimpleNamespace(
        score_diff=0, inning=5, inning_half=0, outs=1, outs_elapsed=24,
        base_state=0, home_pitch_count=70, away_pitch_count=72,
        home_tto=2.0, away_tto=2.0, home_is_bullpen=False, away_is_bullpen=False,
    )
    p1 = {"home_sp_quality": 100, "away_sp_quality": 100,
          "home_sp_recent_form": 0, "away_sp_recent_form": 0,
          "park_run_factor": 1.0, "pregame_prior_source": 0,
          "home_sp_imputed": False, "away_sp_imputed": False}
    p2 = {"current_batter_xwoba": 120, "next3_avg_xwoba": 105,
          "lineup_avg_xwoba": 100, "current_batter_platoon_advantage": 1,
          "current_batter_imputed": False}
    X, feat, q = wi._build_feature_vector(snap, 0.55, p1, p2)
    assert X.shape == (1, 35)
    assert feat["current_batter_xwoba"] == 120
    assert feat["current_batter_platoon_advantage"] == 1.0
    # x_late = (120 - 100) * late_game; late_game = (24/54)**1.5
    expected_late_game = (24/54) ** 1.5
    assert feat["current_batter_xwoba_x_late"] == pytest.approx(20 * expected_late_game)


def test_phase3_feature_names_count():
    from sports.mlb.winprob_inference import _PHASE3_FEATURE_NAMES
    assert len(_PHASE3_FEATURE_NAMES) == 5


def test_build_vector_with_phase3_extras():
    from sports.mlb import winprob_inference as wi
    wi._feature_columns = [
        "pregame_logit","score_diff","abs_score_diff","tied","inning","half","outs",
        "game_progress","late_game","base_state","base_state_value",
        "score_diff_x_late","base_value_x_late","tied_x_late",
        "home_pitch_count_norm","home_tto","home_is_bullpen",
        "away_pitch_count_norm","away_tto","away_is_bullpen",
        "elo_diff_norm","late_tie_bottom",
        "home_sp_quality","away_sp_quality","home_sp_recent_form","away_sp_recent_form",
        "sp_quality_diff","park_run_factor","park_run_factor_x_late","pregame_prior_source",
        "current_batter_xwoba","next3_avg_xwoba","lineup_avg_xwoba",
        "current_batter_platoon_advantage","current_batter_xwoba_x_late",
        "home_reliever_quality","away_reliever_quality",
        "home_bullpen_avg_quality","away_bullpen_avg_quality","leverage_index",
    ]
    snap = SimpleNamespace(
        score_diff=0, inning=9, inning_half=1, outs=2, outs_elapsed=52,
        base_state=7, home_pitch_count=95, away_pitch_count=18,
        home_tto=3.0, away_tto=1.0, home_is_bullpen=False, away_is_bullpen=True,
    )
    p1 = {"home_sp_quality": 95, "away_sp_quality": 110,
          "home_sp_recent_form": 0, "away_sp_recent_form": 0,
          "park_run_factor": 1.0, "pregame_prior_source": 0,
          "home_sp_imputed": False, "away_sp_imputed": False}
    p2 = {"current_batter_xwoba": 100, "next3_avg_xwoba": 100,
          "lineup_avg_xwoba": 100, "current_batter_platoon_advantage": 0,
          "current_batter_imputed": False}
    p3 = {"home_reliever_quality": 95, "away_reliever_quality": 85,
          "home_bullpen_avg_quality": 95, "away_bullpen_avg_quality": 88,
          "leverage_index": 4.5}
    X, feat, q = wi._build_feature_vector(snap, 0.55, p1, p2, p3)
    assert X.shape == (1, 40)
    assert feat["leverage_index"] == 4.5
    assert feat["away_reliever_quality"] == 85


def test_phase4_feature_names_count():
    from sports.mlb.winprob_inference import _PHASE4_FEATURE_NAMES
    assert len(_PHASE4_FEATURE_NAMES) == 5


def test_build_vector_with_phase4_extras():
    from sports.mlb import winprob_inference as wi
    wi._feature_columns = [
        "pregame_logit","score_diff","abs_score_diff","tied","inning","half","outs",
        "game_progress","late_game","base_state","base_state_value",
        "score_diff_x_late","base_value_x_late","tied_x_late",
        "home_pitch_count_norm","home_tto","home_is_bullpen",
        "away_pitch_count_norm","away_tto","away_is_bullpen",
        "elo_diff_norm","late_tie_bottom",
        "home_sp_quality","away_sp_quality","home_sp_recent_form","away_sp_recent_form",
        "sp_quality_diff","park_run_factor",
        "lineup_avg_xwoba",
        "home_reliever_quality","away_reliever_quality",
        "home_bullpen_avg_quality","away_bullpen_avg_quality","leverage_index",
        "wind_out_mph","temp_f","is_roof_closed","in_extras","ghost_runner_on_2nd",
    ]
    snap = SimpleNamespace(
        score_diff=0, inning=11, inning_half=1, outs=0, outs_elapsed=60,
        base_state=0, home_pitch_count=0, away_pitch_count=0,
        home_tto=1.0, away_tto=1.0, home_is_bullpen=True, away_is_bullpen=True,
    )
    p1 = {"home_sp_quality": 100, "away_sp_quality": 100,
          "home_sp_recent_form": 0, "away_sp_recent_form": 0,
          "park_run_factor": 1.0, "pregame_prior_source": 0,
          "home_sp_imputed": False, "away_sp_imputed": False}
    p2 = {"lineup_avg_xwoba": 100,
          "current_batter_imputed": False}
    p3 = {"home_reliever_quality": 100, "away_reliever_quality": 100,
          "home_bullpen_avg_quality": 100, "away_bullpen_avg_quality": 100,
          "leverage_index": 2.0}
    p4 = {"wind_out_mph": 12, "temp_f": 85, "is_roof_closed": 0,
          "ghost_runner_on_2nd": 1}
    X, feat, q = wi._build_feature_vector(snap, 0.55, p1, p2, p3, p4)
    assert X.shape == (1, 39)
    assert feat["wind_out_mph"] == 12
    assert feat["temp_f"] == 85
    assert feat["in_extras"] == 1.0
    assert feat["ghost_runner_on_2nd"] == 1
