"""
models/train_lightgbm.py — LightGBM nonlinear challenger model

Same feature set as logistic baseline. LightGBM can capture:
  - non-linear inning effects
  - interaction between score and game phase without explicit feature engineering
  - pitcher fatigue curves

Hyperparameters are tuned on 2023 validation set (early stopping).

Output:
    artifacts/lgbm_model.pkl   (fitted lgb.Booster)
    artifacts/lgbm_model_meta.json

Usage:
    python -m models.train_lightgbm
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import log_loss, brier_score_loss

logger = logging.getLogger(__name__)

ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", "artifacts"))
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def train_lightgbm(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    feature_names: list[str],
) -> "lgb.Booster":
    """
    Train LightGBM with early stopping on validation set.
    Returns fitted Booster.
    """
    try:
        import lightgbm as lgb
    except ImportError:
        raise ImportError("lightgbm not installed. Run: pip install lightgbm")

    dtrain = lgb.Dataset(X_train, label=y_train, feature_name=feature_names)
    dval = lgb.Dataset(X_val, label=y_val, reference=dtrain, feature_name=feature_names)

    params = {
        "objective": "binary",
        "metric": ["binary_logloss", "auc"],
        "boosting_type": "gbdt",
        "num_leaves": 31,
        "max_depth": 6,
        "learning_rate": 0.05,
        "n_estimators": 1000,
        "min_child_samples": 100,   # prevent overfitting on sparse PA states
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "random_state": 42,
        "verbose": -1,
    }

    logger.info("Training LightGBM (early stopping patience=50) ...")
    callbacks = [
        lgb.early_stopping(stopping_rounds=50, verbose=True),
        lgb.log_evaluation(period=100),
    ]

    booster = lgb.train(
        params,
        dtrain,
        num_boost_round=params["n_estimators"],
        valid_sets=[dval],
        valid_names=["val"],
        callbacks=callbacks,
    )

    # Feature importance
    imp_df = pd.DataFrame({
        "feature": feature_names,
        "importance_gain": booster.feature_importance(importance_type="gain"),
        "importance_split": booster.feature_importance(importance_type="split"),
    }).sort_values("importance_gain", ascending=False)
    logger.info("Top 10 feature importances (gain):\n%s", imp_df.head(10).to_string(index=False))

    return booster


def main():
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Train LightGBM challenger model")
    parser.add_argument("--train-seasons", nargs="+", type=int, default=list(range(2018, 2023)))
    parser.add_argument("--val-seasons", nargs="+", type=int, default=[2023])
    args = parser.parse_args()

    from data.feature_store import load_feature_store, FEATURE_COLUMNS, TARGET_COLUMN

    logger.info("Loading feature store ...")
    features = load_feature_store()

    train_df = features[features["season"].isin(args.train_seasons)]
    val_df = features[features["season"].isin(args.val_seasons)]

    logger.info("Train: %d rows | Val: %d rows", len(train_df), len(val_df))

    X_train = train_df[FEATURE_COLUMNS].values
    y_train = train_df[TARGET_COLUMN].values
    X_val = val_df[FEATURE_COLUMNS].values
    y_val = val_df[TARGET_COLUMN].values

    booster = train_lightgbm(X_train, y_train, X_val, y_val, FEATURE_COLUMNS)

    # Evaluate
    val_probs = booster.predict(X_val)
    val_log_loss = log_loss(y_val, val_probs)
    val_brier = brier_score_loss(y_val, val_probs)

    # Prior baseline
    prior_logit = X_val[:, FEATURE_COLUMNS.index("pregame_logit")]
    prior_probs = 1 / (1 + np.exp(-prior_logit))
    prior_log_loss = log_loss(y_val, prior_probs)
    prior_brier = brier_score_loss(y_val, prior_probs)

    logger.info("=== Validation Results ===")
    logger.info("Prior-only   log_loss=%.6f  brier=%.6f", prior_log_loss, prior_brier)
    logger.info("LightGBM     log_loss=%.6f  brier=%.6f  (improvement: %.4f / %.4f)",
                val_log_loss, val_brier,
                prior_log_loss - val_log_loss,
                prior_brier - val_brier)

    # Save
    model_path = ARTIFACT_DIR / "lgbm_model.pkl"
    joblib.dump(booster, model_path)
    logger.info("Saved model: %s", model_path)

    meta = {
        "model_type": "lightgbm",
        "best_n_estimators": booster.num_trees(),
        "train_seasons": args.train_seasons,
        "val_seasons": args.val_seasons,
        "val_log_loss": val_log_loss,
        "val_brier": val_brier,
        "prior_log_loss": prior_log_loss,
        "prior_brier": prior_brier,
        "improvement_log_loss": prior_log_loss - val_log_loss,
        "improvement_brier": prior_brier - val_brier,
        "n_train": len(train_df),
        "n_val": len(val_df),
        "feature_columns": FEATURE_COLUMNS,
    }
    meta_path = ARTIFACT_DIR / "lgbm_model_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    logger.info("Saved metadata: %s", meta_path)


if __name__ == "__main__":
    main()
