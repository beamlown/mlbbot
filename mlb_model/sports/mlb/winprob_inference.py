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
    snapshot: "GameStateSnapshot",
    pregame_win_prob: float,
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

    # Data quality: penalize for missing features
    quality = 1.0
    if snapshot.home_pitch_count == 0 and snapshot.away_pitch_count == 0:
        quality -= 0.05   # no pitch count data
    if snapshot.base_state == 0 and snapshot.inning > 1:
        quality -= 0.02   # base state may not be populated
    if pregame_win_prob == 0.54:
        quality -= 0.05   # using default prior, not Elo-calibrated

    quality = max(0.0, quality)

    # Build array in exact feature column order
    X = np.array([[feat[col] for col in _feature_columns]], dtype=np.float64)
    return X, feat, quality


def infer(
    snapshot: "GameStateSnapshot",
    pregame_win_prob: float = 0.54,
) -> InferenceResult:
    """
    Run inference on a live game state.
    Returns calibrated P(home wins) from the model's perspective.
    pregame_win_prob: P(home wins) before the game started.
    """
    if _model is None or _calibrator is None:
        raise RuntimeError("Model artifacts not loaded. Call load_artifacts() first.")

    X, feat_dict, quality = _build_feature_vector(snapshot, pregame_win_prob)

    # Raw prediction
    if hasattr(_model, "predict_proba"):
        raw_prob = float(_model.predict_proba(X)[0, 1])
    else:
        # LightGBM booster
        raw_prob = float(_model.predict(X)[0])

    # Calibrated probability
    cal_prob = float(_calibrator.predict(np.array([raw_prob])))

    # Clip to reasonable range
    cal_prob = max(0.01, min(0.99, cal_prob))

    return InferenceResult(
        p_home=round(cal_prob, 6),
        p_away=round(1.0 - cal_prob, 6),
        raw_prob=round(raw_prob, 6),
        features=feat_dict,
        model_version=_manifest.get("model_version", "mlb_winprob_v1"),
        data_quality=round(quality, 4),
    )


def is_loaded() -> bool:
    return _model is not None and _calibrator is not None


# ── Convenience: infer for tracked team (home or away) ────────────────────────

def infer_for_team(
    snapshot: "GameStateSnapshot",
    tracked_team: str,
    pregame_win_prob_home: float = 0.54,
) -> tuple[float, InferenceResult]:
    """
    Return calibrated P(tracked_team wins) regardless of home/away.
    Also returns the full InferenceResult for logging.
    """
    from sports.mlb.team_normalizer import normalize
    result = infer(snapshot, pregame_win_prob_home)

    tracked = normalize(tracked_team)
    if tracked == snapshot.home_team:
        p_tracked = result.p_home
    else:
        p_tracked = result.p_away

    return round(p_tracked, 6), result
