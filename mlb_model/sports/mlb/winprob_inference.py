"""
sports/mlb/winprob_inference.py — Live win probability inference

Loads trained + calibrated model artifacts and computes P(home wins | live state).

Given a GameStateSnapshot and a pregame prior, returns:
    p_home: float   calibrated P(home team wins)
    p_away: float   1 - p_home
    features: dict  feature vector used (for logging/debugging)
    model_version: str

The inference pipeline:
    1. Build feature vector from GameStateSnapshot + pregame_win_prob
    2. Call raw model predict
    3. Apply calibrator
    4. Return calibrated probability

Artifacts loaded (from ARTIFACT_DIR):
    winprob_model.pkl    (logistic Pipeline or lgb.Booster)
    calibrator.pkl       (PlattCalibrator or IsotonicCalibrator)
    deployment_manifest.json

Public API:
    load_artifacts() -> None            (call at startup)
    infer(snapshot, pregame_prob) -> InferenceResult
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", "artifacts"))

_model = None
_calibrator = None
_manifest: dict = {}
_feature_columns: list[str] = []

# Base state run expectancy weights (matches feature_store.py)
_BASE_STATE_VALUE = {0: 0.0, 1: 0.9, 2: 1.1, 3: 1.3, 4: 1.6, 5: 1.8, 6: 1.9, 7: 2.3}

_PHASE1_FEATURE_NAMES = (
    "home_sp_quality", "away_sp_quality",
    "home_sp_recent_form", "away_sp_recent_form",
    "sp_quality_diff", "park_run_factor",
    "park_run_factor_x_late", "pregame_prior_source",
)
_PHASE2_FEATURE_NAMES = (
    "current_batter_xwoba", "next3_avg_xwoba", "lineup_avg_xwoba",
    "current_batter_platoon_advantage", "current_batter_xwoba_x_late",
)
_PHASE3_FEATURE_NAMES = (
    "home_reliever_quality", "away_reliever_quality",
    "home_bullpen_avg_quality", "away_bullpen_avg_quality",
    "leverage_index",
)
_PHASE4_FEATURE_NAMES = (
    "wind_out_mph", "temp_f", "is_roof_closed",
    "in_extras", "ghost_runner_on_2nd",
)


@dataclass
class InferenceResult:
    p_home: float               # P(home team wins)
    p_away: float               # P(away team wins) = 1 - p_home
    raw_prob: float             # pre-calibration model output
    features: dict[str, float]  # feature vector for audit logging
    model_version: str
    data_quality: float         # 0-1 confidence in feature completeness


def load_artifacts() -> None:
    """Load model and calibrator from disk. Call once at startup."""
    global _model, _calibrator, _manifest, _feature_columns
    import joblib

    manifest_path = ARTIFACT_DIR / "deployment_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Deployment manifest not found at {manifest_path}. "
            "Run models/export_artifacts.py first."
        )
    with open(manifest_path) as f:
        _manifest = json.load(f)

    _feature_columns = _manifest["feature_columns"]

    model_path = ARTIFACT_DIR / "winprob_model.pkl"
    cal_path = ARTIFACT_DIR / "calibrator.pkl"

    _model = joblib.load(model_path)
    _calibrator = joblib.load(cal_path)
    logger.info("Loaded model artifacts: version=%s  features=%d",
                _manifest.get("model_version", "unknown"), len(_feature_columns))


def _safe_logit(p: float) -> float:
    p = max(1e-6, min(1 - 1e-6, p))
    return float(np.log(p / (1 - p)))


def _build_feature_vector(
    snapshot,
    pregame_win_prob: float,
    phase1_extras: dict | None = None,
    phase2_extras: dict | None = None,
    phase3_extras: dict | None = None,
    phase4_extras: dict | None = None,
) -> tuple[np.ndarray, dict[str, float], float]:
    """
    Convert a GameStateSnapshot to the model's feature vector.
    Returns (X, feature_dict, data_quality).
    """
    from sports.mlb.game_state_service import GameStateSnapshot

    # Game progress
    outs_el = snapshot.outs_elapsed
    game_progress = min(1.0, outs_el / 54.0)
    late_game = game_progress ** 1.5

    # Base state value
    bs_val = _BASE_STATE_VALUE.get(snapshot.base_state, 0.0)

    # Score
    score_diff = float(snapshot.score_diff)
    tied = 1.0 if score_diff == 0 else 0.0

    # Pitcher features
    home_pc_norm = snapshot.home_pitch_count / 100.0
    away_pc_norm = snapshot.away_pitch_count / 100.0
    home_tto = float(snapshot.home_tto)
    away_tto = float(snapshot.away_tto)
    home_bullpen = 1.0 if snapshot.home_is_bullpen else 0.0
    away_bullpen = 1.0 if snapshot.away_is_bullpen else 0.0

    # Team strength: convert pregame probability back to Elo-difference scale.
    # Training feature: (home_elo - away_elo) / 400
    # Elo math: logit_e(p) = (elo_diff / 400) * ln(10)
    # Therefore: elo_diff / 400 = logit_e(p) / ln(10)
    # ln(10) = 2.302585
    elo_diff_norm = _safe_logit(pregame_win_prob) / 2.302585

    # Late tie bottom
    late_tie_bottom = (
        float(snapshot.inning >= 9) *
        float(snapshot.inning_half == 1) *
        tied
    )

    feat = {
        "pregame_logit": _safe_logit(pregame_win_prob),
        "score_diff": score_diff,
        "abs_score_diff": abs(score_diff),
        "tied": tied,
        "inning": float(snapshot.inning),
        "half": float(snapshot.inning_half),
        "outs": float(snapshot.outs),
        "game_progress": game_progress,
        "late_game": late_game,
        "base_state": float(snapshot.base_state),
        "base_state_value": bs_val,
        "score_diff_x_late": score_diff * late_game,
        "base_value_x_late": bs_val * late_game,
        "tied_x_late": tied * late_game,
        "home_pitch_count_norm": home_pc_norm,
        "home_tto": home_tto,
        "home_is_bullpen": home_bullpen,
        "away_pitch_count_norm": away_pc_norm,
        "away_tto": away_tto,
        "away_is_bullpen": away_bullpen,
        "elo_diff_norm": elo_diff_norm,
        "late_tie_bottom": late_tie_bottom,
    }

    # Phase-1 features
    extras = phase1_extras or {}
    feat["home_sp_quality"] = float(extras.get("home_sp_quality", 100.0))
    feat["away_sp_quality"] = float(extras.get("away_sp_quality", 100.0))
    feat["home_sp_recent_form"] = float(extras.get("home_sp_recent_form", 0.0))
    feat["away_sp_recent_form"] = float(extras.get("away_sp_recent_form", 0.0))
    feat["sp_quality_diff"] = feat["away_sp_quality"] - feat["home_sp_quality"]
    feat["park_run_factor"] = float(extras.get("park_run_factor", 1.0))
    feat["park_run_factor_x_late"] = (feat["park_run_factor"] - 1.0) * feat["late_game"]
    feat["pregame_prior_source"] = float(extras.get("pregame_prior_source", 1))

    # Phase-2 batter features
    p2 = phase2_extras or {}
    feat["current_batter_xwoba"] = float(p2.get("current_batter_xwoba", 100.0))
    feat["next3_avg_xwoba"] = float(p2.get("next3_avg_xwoba", 100.0))
    feat["lineup_avg_xwoba"] = float(p2.get("lineup_avg_xwoba", 100.0))
    feat["current_batter_platoon_advantage"] = float(p2.get("current_batter_platoon_advantage", 0.0))
    feat["current_batter_xwoba_x_late"] = (feat["current_batter_xwoba"] - 100.0) * feat["late_game"]

    # Phase-3 bullpen + leverage
    p3 = phase3_extras or {}
    feat["home_reliever_quality"] = float(p3.get("home_reliever_quality", feat.get("home_sp_quality", 100.0)))
    feat["away_reliever_quality"] = float(p3.get("away_reliever_quality", feat.get("away_sp_quality", 100.0)))
    feat["home_bullpen_avg_quality"] = float(p3.get("home_bullpen_avg_quality", 100.0))
    feat["away_bullpen_avg_quality"] = float(p3.get("away_bullpen_avg_quality", 100.0))
    feat["leverage_index"] = float(p3.get("leverage_index", 1.0))

    # Phase-4 weather + extras
    p4 = phase4_extras or {}
    feat["wind_out_mph"] = float(p4.get("wind_out_mph", 0.0))
    feat["temp_f"] = float(p4.get("temp_f", 70.0))
    feat["is_roof_closed"] = float(p4.get("is_roof_closed", 1.0))
    feat["in_extras"] = 1.0 if float(snapshot.inning) > 9 else 0.0
    feat["ghost_runner_on_2nd"] = float(p4.get("ghost_runner_on_2nd", 0.0))

    quality = 1.0
    if snapshot.home_pitch_count == 0 and snapshot.away_pitch_count == 0:
        quality -= 0.05
    if snapshot.base_state == 0 and snapshot.inning > 1:
        quality -= 0.02
    src = int(feat["pregame_prior_source"])
    if src == 1:
        quality -= 0.03   # elo (less sharp than Pinnacle)
    elif src == 2:
        quality -= 0.10   # full default — visible penalty
    if extras.get("home_sp_imputed") or extras.get("away_sp_imputed"):
        quality -= 0.05
    if p2.get("current_batter_imputed"):
        quality -= 0.03
    quality = max(0.0, quality)

    # Build array in exact feature column order
    X = np.array([[feat[col] for col in _feature_columns]], dtype=np.float64)
    return X, feat, quality


def infer(snapshot, pregame_win_prob: float = 0.54,
          phase1_extras: dict | None = None,
          phase2_extras: dict | None = None,
          phase3_extras: dict | None = None,
          phase4_extras: dict | None = None) -> InferenceResult:
    if _model is None or _calibrator is None:
        raise RuntimeError("Model artifacts not loaded.")
    X, feat_dict, quality = _build_feature_vector(snapshot, pregame_win_prob,
                                                   phase1_extras, phase2_extras,
                                                   phase3_extras, phase4_extras)
    if hasattr(_model, "predict_proba"):
        raw_prob = float(_model.predict_proba(X)[0, 1])
    else:
        raw_prob = float(_model.predict(X)[0])
    cal_prob = float(_calibrator.predict(np.array([raw_prob])))
    cal_prob = max(0.01, min(0.99, cal_prob))
    return InferenceResult(
        p_home=round(cal_prob, 6), p_away=round(1.0 - cal_prob, 6),
        raw_prob=round(raw_prob, 6), features=feat_dict,
        model_version=_manifest.get("model_version", "mlb_winprob_v1"),
        data_quality=round(quality, 4),
    )


def is_loaded() -> bool:
    return _model is not None and _calibrator is not None


# ── Convenience: infer for tracked team (home or away) ────────────────────────

def infer_for_team(snapshot, tracked_team, pregame_win_prob_home: float = 0.54,
                   phase1_extras: dict | None = None,
                   phase2_extras: dict | None = None,
                   phase3_extras: dict | None = None,
                   phase4_extras: dict | None = None):
    from sports.mlb.team_normalizer import normalize
    result = infer(snapshot, pregame_win_prob_home,
                   phase1_extras, phase2_extras, phase3_extras, phase4_extras)
    tracked = normalize(tracked_team)
    p_tracked = result.p_home if tracked == snapshot.home_team else result.p_away
    return round(p_tracked, 6), result
