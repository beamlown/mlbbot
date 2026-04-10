"""
models/train_logistic_baseline.py — Logistic regression baseline model

Trains on 2018–2022 data, validates on 2023.

Model shape (per spec):
    logit(p_live) = logit(p_pregame) + f(live_features)

Since pregame_logit is already one of the features, standard logistic
regression on FEATURE_COLUMNS achieves this shape naturally.

Regularization: L2 with C tuned on validation set.

Output:
    artifacts/logistic_baseline.pkl   (fitted sklearn Pipeline)
    artifacts/logistic_baseline_meta.json

Usage:
    python -m models.train_logistic_baseline
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, brier_score_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", "artifacts"))
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def train_logistic(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    feature_names: list[str],
) -> Pipeline:
    """
    Train a logistic regression model with C tuned on validation set.
    Returns the best fitted Pipeline (StandardScaler + LogisticRegression).
    """
    # C search: wider range to find proper regularization
    c_candidates = [0.01, 0.05, 0.1, 0.3, 1.0, 3.0, 10.0]
    best_c = 0.1
    best_val_loss = float("inf")

    logger.info("Tuning C on validation set (%d rows) ...", len(X_val))
    for c in c_candidates:
        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("lr", LogisticRegression(C=c, max_iter=1000, solver="lbfgs", random_state=42)),
        ])
        pipe.fit(X_train, y_train)
        val_probs = pipe.predict_proba(X_val)[:, 1]
        val_loss = log_loss(y_val, val_probs)
        logger.info("  C=%.4f  val_log_loss=%.6f", c, val_loss)
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_c = c

    logger.info("Best C=%.4f (val_log_loss=%.6f)", best_c, best_val_loss)

    # Refit on train+val combined for final model
    X_all = np.vstack([X_train, X_val])
    y_all = np.concatenate([y_train, y_val])
    final_pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(C=best_c, max_iter=1000, solver="lbfgs", random_state=42)),
    ])
    final_pipe.fit(X_all, y_all)

    # Log coefficients for interpretability
    lr = final_pipe.named_steps["lr"]
    coef_df = pd.DataFrame({
        "feature": feature_names,
        "coef": lr.coef_[0],
    }).sort_values("coef", key=abs, ascending=False)
    logger.info("Top 10 feature coefficients:\n%s", coef_df.head(10).to_string(index=False))

    return final_pipe, best_c, best_val_loss


def main():
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Train logistic regression baseline")
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

    pipe, best_c, best_val_loss = train_logistic(X_train, y_train, X_val, y_val, FEATURE_COLUMNS)

    # Evaluate on validation set
    val_probs = pipe.predict_proba(X_val)[:, 1]
    val_log_loss = log_loss(y_val, val_probs)
    val_brier = brier_score_loss(y_val, val_probs)

    # Compare against pregame prior baseline
    prior_col = FEATURE_COLUMNS.index("pregame_logit")
    prior_logit = X_val[:, prior_col]
    prior_probs = 1 / (1 + np.exp(-prior_logit))
    prior_log_loss = log_loss(y_val, prior_probs)
    prior_brier = brier_score_loss(y_val, prior_probs)

    logger.info("=== Validation Results ===")
    logger.info("Prior-only   log_loss=%.6f  brier=%.6f", prior_log_loss, prior_brier)
    logger.info("Logistic     log_loss=%.6f  brier=%.6f  (improvement: %.4f / %.4f)",
                val_log_loss, val_brier,
                prior_log_loss - val_log_loss,
                prior_brier - val_brier)

    # Save model
    model_path = ARTIFACT_DIR / "logistic_baseline.pkl"
    joblib.dump(pipe, model_path)
    logger.info("Saved model: %s", model_path)

    meta = {
        "model_type": "logistic_regression",
        "best_c": best_c,
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
    meta_path = ARTIFACT_DIR / "logistic_baseline_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    logger.info("Saved metadata: %s", meta_path)


if __name__ == "__main__":
    main()
