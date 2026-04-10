"""
data/feature_store.py — Feature engineering and dataset assembly

Takes raw snapshot rows and engineers the final model features:
  - Log-odds transform of pregame prior (pregame_logit)
  - Interaction terms (score_diff * late_game, etc.)
  - Normalized pitch counts
  - Late game flag
  - All features are stored in a single parquet in FEATURE_DIR

This is the authoritative feature list. Any change here must be reflected in
feature_schema.json and winprob_inference.py.

Usage:
    python -m data.feature_store --seasons 2018 2019 2020 2021 2022 2023 2024 2025
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

FEATURE_DIR = Path(os.getenv("FEATURE_DIR", "data/features"))
ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", "artifacts"))

# These are the exact features fed to the model — in this exact order.
# Change this list only when retraining everything from scratch.
FEATURE_COLUMNS = [
    # Pregame prior
    "pregame_logit",           # logit(pregame_win_prob)

    # Score state
    "score_diff",              # home_score - away_score
    "abs_score_diff",          # |score_diff|
    "tied",                    # 1 if score_diff == 0

    # Time / inning
    "inning",                  # 1-9+
    "half",                    # 0=top, 1=bottom
    "outs",                    # 0-2
    "game_progress",           # outs_elapsed / 54 (capped 1.0)
    "late_game",               # game_progress^1.5

    # Base runners
    "base_state",              # 0-7
    "base_state_value",        # run expectancy weight

    # Interaction terms
    "score_diff_x_late",       # score_diff * late_game
    "base_value_x_late",       # base_state_value * late_game
    "tied_x_late",             # tied * late_game

    # Pitcher features — home
    "home_pitch_count_norm",   # home_pitch_count / 100
    "home_tto",                # times through order proxy
    "home_is_bullpen",         # 0/1

    # Pitcher features — away
    "away_pitch_count_norm",   # away_pitch_count / 100
    "away_tto",
    "away_is_bullpen",

    # Team strength (Elo-derived)
    "elo_diff_norm",           # (home_elo - away_elo) / 400

    # Bottom of 9+ tied: classic extra innings setup
    "late_tie_bottom",         # (inning >= 9) * (half == 1) * tied
]

TARGET_COLUMN = "home_won_final"


def _safe_logit(p: float | pd.Series, eps: float = 1e-6) -> float | pd.Series:
    p = np.clip(p, eps, 1 - eps)
    return np.log(p / (1 - p))


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Takes raw snapshot DataFrame and returns feature-engineered DataFrame
    with FEATURE_COLUMNS + TARGET_COLUMN.
    """
    out = pd.DataFrame(index=df.index)

    # Pregame prior
    out["pregame_logit"] = _safe_logit(df["pregame_win_prob"])

    # Score
    out["score_diff"] = df["score_diff"].astype(float)
    out["abs_score_diff"] = out["score_diff"].abs()
    out["tied"] = (out["score_diff"] == 0).astype(float)

    # Time / inning
    out["inning"] = df["inning"].astype(float)
    out["half"] = df["half"].astype(float)
    out["outs"] = df["outs"].astype(float)
    out["game_progress"] = df["game_progress"].astype(float).clip(0, 1)
    out["late_game"] = out["game_progress"] ** 1.5

    # Base runners
    out["base_state"] = df["base_state"].astype(float)
    out["base_state_value"] = df["base_state_value"].astype(float)

    # Interactions
    out["score_diff_x_late"] = out["score_diff"] * out["late_game"]
    out["base_value_x_late"] = out["base_state_value"] * out["late_game"]
    out["tied_x_late"] = out["tied"] * out["late_game"]

    # Pitcher features
    out["home_pitch_count_norm"] = df["home_pitch_count"].astype(float) / 100.0
    out["home_tto"] = df["home_tto"].astype(float)
    out["home_is_bullpen"] = df["home_is_bullpen"].astype(float)

    out["away_pitch_count_norm"] = df["away_pitch_count"].astype(float) / 100.0
    out["away_tto"] = df["away_tto"].astype(float)
    out["away_is_bullpen"] = df["away_is_bullpen"].astype(float)

    # Team strength
    out["elo_diff_norm"] = (df["home_elo"] - df["away_elo"]) / 400.0

    # Late tie
    out["late_tie_bottom"] = (
        (df["inning"] >= 9).astype(float) *
        (df["half"] == 1).astype(float) *
        out["tied"]
    )

    # Target
    out[TARGET_COLUMN] = df[TARGET_COLUMN].astype(int)

    # Metadata (not features, but useful for analysis)
    for meta_col in ["game_id", "date", "season", "home_team", "away_team"]:
        if meta_col in df.columns:
            out[meta_col] = df[meta_col]

    # Validate no NaN in feature columns
    nan_counts = out[FEATURE_COLUMNS].isna().sum()
    if nan_counts.any():
        bad_cols = nan_counts[nan_counts > 0]
        logger.warning("NaN values in features: %s — filling with 0", bad_cols.to_dict())
        out[FEATURE_COLUMNS] = out[FEATURE_COLUMNS].fillna(0.0)

    return out


def build_feature_store(seasons: list[int]) -> pd.DataFrame:
    """Load snapshot files, engineer features, combine, and save."""
    from data.state_snapshot_builder import load_snapshots

    logger.info("Building feature store for seasons: %s", seasons)
    raw = load_snapshots(seasons)
    if raw.empty:
        raise ValueError("No snapshot data found. Run state_snapshot_builder first.")

    logger.info("Raw snapshots: %d rows", len(raw))
    features = engineer_features(raw)
    logger.info("Engineered features: %d rows, %d feature columns", len(features), len(FEATURE_COLUMNS))

    # Save
    FEATURE_DIR.mkdir(parents=True, exist_ok=True)
    path = FEATURE_DIR / "features_all.parquet"
    features.to_parquet(path, index=False)
    logger.info("Saved feature store: %s", path)

    # Save feature schema for inference
    schema = {
        "feature_columns": FEATURE_COLUMNS,
        "target_column": TARGET_COLUMN,
        "n_features": len(FEATURE_COLUMNS),
        "seasons": sorted(features["season"].unique().tolist()) if "season" in features.columns else seasons,
        "n_rows": len(features),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    schema_path = ARTIFACT_DIR / "feature_schema.json"
    with open(schema_path, "w") as f:
        json.dump(schema, f, indent=2)
    logger.info("Saved feature schema: %s", schema_path)

    return features


def load_feature_store() -> pd.DataFrame:
    path = FEATURE_DIR / "features_all.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Feature store not found at {path}. Run feature_store.py first.")
    return pd.read_parquet(path)


def get_time_splits(features: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Return time-based train/tune/calibrate/test splits (as in the spec).
    Seasons: Train 2018-2022, Tune 2023, Calibrate 2024, Test 2025
    """
    if "season" not in features.columns:
        raise ValueError("Feature store must contain 'season' column")

    train_seasons = list(range(2018, 2023))
    tune_seasons = [2023]
    calibrate_seasons = [2024]
    test_seasons = [2025]

    splits = {}
    for name, season_list in [
        ("train", train_seasons),
        ("tune", tune_seasons),
        ("calibrate", calibrate_seasons),
        ("test", test_seasons),
    ]:
        mask = features["season"].isin(season_list)
        splits[name] = features[mask].reset_index(drop=True)
        logger.info("Split '%s': %d rows (seasons %s)", name, len(splits[name]), season_list)

    return splits


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Build feature store from snapshots")
    parser.add_argument("--seasons", nargs="+", type=int,
                        default=list(range(2018, 2026)))
    args = parser.parse_args()

    features = build_feature_store(args.seasons)
    splits = get_time_splits(features)

    # Quick sanity stats
    for name, split in splits.items():
        if not split.empty:
            hw_rate = split[TARGET_COLUMN].mean()
            logger.info("Split '%s': n=%d, home_win_rate=%.4f", name, len(split), hw_rate)


if __name__ == "__main__":
    main()
