"""
models/calibrate_model.py — Probability calibration layer

Takes raw model predictions and fits a calibration map so that predicted
probabilities match observed win rates.

Two calibration methods compared:
  1. Platt scaling (sigmoid): sklearn CalibratedClassifierCV with method='sigmoid'
     on a held-out calibration set. Equivalent to logistic regression on raw logits.
  2. Isotonic regression: more flexible, monotone mapping.
     Can overfit with small calibration sets — use with caution.

The calibration set is 2024 (separate from train 2018–2022 and val 2023).
The final held-out test set is 2025 — never used during calibration.

Selection rule: use sigmoid by default unless isotonic shows materially better
reliability curve without signs of overfitting.

Output:
    artifacts/calibrator_{model_type}.pkl    (fitted calibrator object)
    artifacts/calibration_meta.json

Usage:
    python -m models.calibrate_model --model logistic   # or --model lgbm
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, brier_score_loss

logger = logging.getLogger(__name__)

ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", "artifacts"))


def _raw_predict(model_type: str, X: np.ndarray) -> np.ndarray:
    """Get raw (uncalibrated) predictions from saved model."""
    if model_type == "logistic":
        pipe = joblib.load(ARTIFACT_DIR / "logistic_baseline.pkl")
        return pipe.predict_proba(X)[:, 1]
    elif model_type == "lgbm":
        booster = joblib.load(ARTIFACT_DIR / "lgbm_model.pkl")
        return booster.predict(X)
    else:
        raise ValueError(f"Unknown model_type: {model_type}")


class PlattCalibrator:
    """Logistic regression on raw predictions (Platt scaling)."""

    def __init__(self):
        self._lr = LogisticRegression(C=1.0, solver="lbfgs")

    def fit(self, raw_probs: np.ndarray, y: np.ndarray) -> "PlattCalibrator":
        logits = np.log(np.clip(raw_probs, 1e-7, 1 - 1e-7) / (1 - np.clip(raw_probs, 1e-7, 1 - 1e-7)))
        self._lr.fit(logits.reshape(-1, 1), y)
        return self

    def predict(self, raw_probs: np.ndarray) -> np.ndarray:
        logits = np.log(np.clip(raw_probs, 1e-7, 1 - 1e-7) / (1 - np.clip(raw_probs, 1e-7, 1 - 1e-7)))
        return self._lr.predict_proba(logits.reshape(-1, 1))[:, 1]


class IsotonicCalibrator:
    """Monotone isotonic regression calibration."""

    def __init__(self):
        self._iso = IsotonicRegression(out_of_bounds="clip")

    def fit(self, raw_probs: np.ndarray, y: np.ndarray) -> "IsotonicCalibrator":
        self._iso.fit(raw_probs, y)
        return self

    def predict(self, raw_probs: np.ndarray) -> np.ndarray:
        return self._iso.predict(raw_probs)


def calibrate_and_compare(
    raw_probs_cal: np.ndarray,
    y_cal: np.ndarray,
) -> tuple[object, str]:
    """
    Fit both calibration methods on the first half of the calibration set,
    compare on the second half (held-out), and return the better calibrator
    fit on the full calibration set.

    Splitting within the calibration year keeps time ordering correct —
    the first half of 2024 trains, the second half of 2024 validates.
    This avoids using 2023 val data (which was already used for C-selection).
    """
    n = len(raw_probs_cal)
    split = n // 2

    fit_raw, fit_y     = raw_probs_cal[:split], y_cal[:split]
    check_raw, check_y = raw_probs_cal[split:],  y_cal[split:]

    # Fit on first half of cal set
    platt_tmp = PlattCalibrator().fit(fit_raw, fit_y)
    iso_tmp   = IsotonicCalibrator().fit(fit_raw, fit_y)

    # Compare on second half of cal set
    platt_ll = log_loss(check_y, platt_tmp.predict(check_raw))
    iso_ll   = log_loss(check_y, iso_tmp.predict(check_raw))
    platt_bs = brier_score_loss(check_y, platt_tmp.predict(check_raw))
    iso_bs   = brier_score_loss(check_y, iso_tmp.predict(check_raw))

    logger.info("Calibration comparison on cal-set holdout (second half of cal year):")
    logger.info("  Platt:    log_loss=%.6f  brier=%.6f", platt_ll, platt_bs)
    logger.info("  Isotonic: log_loss=%.6f  brier=%.6f", iso_ll, iso_bs)

    # Choose method; use sigmoid unless isotonic is materially better
    use_isotonic = iso_ll < platt_ll - 0.001

    # Refit winner on the FULL calibration set for deployment
    if use_isotonic:
        logger.info("Selecting isotonic calibration (materially better on cal holdout)")
        final = IsotonicCalibrator().fit(raw_probs_cal, y_cal)
        return final, "isotonic"
    else:
        logger.info("Selecting Platt (sigmoid) calibration")
        final = PlattCalibrator().fit(raw_probs_cal, y_cal)
        return final, "sigmoid"


def reliability_summary(probs: np.ndarray, y: np.ndarray, n_bins: int = 10) -> dict:
    """Compute per-bin predicted vs actual win rate for reliability diagram."""
    frac_pos, mean_pred = calibration_curve(y, probs, n_bins=n_bins, strategy="uniform")
    return {
        "bins": n_bins,
        "mean_predicted": mean_pred.tolist(),
        "fraction_positive": frac_pos.tolist(),
        "max_calibration_error": float(np.abs(frac_pos - mean_pred).max()),
        "mean_calibration_error": float(np.abs(frac_pos - mean_pred).mean()),
    }


def main():
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Calibrate trained model")
    parser.add_argument("--model", choices=["logistic", "lgbm"], default="lgbm")
    parser.add_argument("--cal-seasons", nargs="+", type=int, default=[2024])
    parser.add_argument("--val-seasons", nargs="+", type=int, default=[2023])
    args = parser.parse_args()

    from data.feature_store import load_feature_store, FEATURE_COLUMNS, TARGET_COLUMN

    logger.info("Loading feature store for calibration ...")
    features = load_feature_store()

    cal_df = features[features["season"].isin(args.cal_seasons)]
    val_df = features[features["season"].isin(args.val_seasons)]

    logger.info("Cal set: %d rows | Val set: %d rows", len(cal_df), len(val_df))

    X_cal = cal_df[FEATURE_COLUMNS].values
    y_cal = cal_df[TARGET_COLUMN].values
    X_val = val_df[FEATURE_COLUMNS].values
    y_val = val_df[TARGET_COLUMN].values

    # Raw predictions
    raw_cal = _raw_predict(args.model, X_cal)
    raw_val = _raw_predict(args.model, X_val)

    # Log pre-calibration performance
    raw_ll_cal = log_loss(y_cal, raw_cal)
    raw_bs_cal = brier_score_loss(y_cal, raw_cal)
    logger.info("Pre-calibration on cal set: log_loss=%.6f  brier=%.6f", raw_ll_cal, raw_bs_cal)

    # Calibrate (method selected on internal cal-set holdout — no val-set contamination)
    calibrator, method = calibrate_and_compare(raw_cal, y_cal)

    # Post-calibration eval on cal set
    cal_probs = calibrator.predict(raw_cal)
    cal_ll = log_loss(y_cal, cal_probs)
    cal_bs = brier_score_loss(y_cal, cal_probs)
    logger.info("Post-calibration on cal set: log_loss=%.6f  brier=%.6f", cal_ll, cal_bs)

    # Reliability stats
    rel = reliability_summary(cal_probs, y_cal)
    logger.info("Calibration set reliability: max_error=%.4f  mean_error=%.4f",
                rel["max_calibration_error"], rel["mean_calibration_error"])

    # Save calibrator
    cal_path = ARTIFACT_DIR / f"calibrator_{args.model}.pkl"
    joblib.dump(calibrator, cal_path)
    logger.info("Saved calibrator: %s", cal_path)

    # Also save as the "active" calibrator (used by inference)
    active_cal_path = ARTIFACT_DIR / "calibrator.pkl"
    joblib.dump(calibrator, active_cal_path)

    meta = {
        "model_type": args.model,
        "calibration_method": method,
        "cal_seasons": args.cal_seasons,
        "val_seasons": args.val_seasons,
        "raw_log_loss_cal": raw_ll_cal,
        "raw_brier_cal": raw_bs_cal,
        "cal_log_loss": cal_ll,
        "cal_brier": cal_bs,
        "reliability": rel,
        "n_cal": len(cal_df),
    }
    meta_path = ARTIFACT_DIR / "calibration_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    logger.info("Saved calibration metadata: %s", meta_path)


if __name__ == "__main__":
    main()
