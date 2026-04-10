"""
models/evaluate_model.py — Full model evaluation on holdout test set (2025)

Runs the calibrated model against the 2025 holdout and produces:
  - Log loss, Brier score vs prior baseline
  - Reliability curve (calibration plot)
  - Edge bucket analysis (binned by model_prob - 0.5)
  - Per-inning breakdown
  - Promotion check (does model meet all criteria?)
  - Saves artifacts/model_report.md

Usage:
    python -m models.evaluate_model --model lgbm   # or logistic
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import log_loss, brier_score_loss

logger = logging.getLogger(__name__)

ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", "artifacts"))


def _raw_predict(model_type: str, X: np.ndarray) -> np.ndarray:
    if model_type == "logistic":
        pipe = joblib.load(ARTIFACT_DIR / "logistic_baseline.pkl")
        return pipe.predict_proba(X)[:, 1]
    elif model_type == "lgbm":
        booster = joblib.load(ARTIFACT_DIR / "lgbm_model.pkl")
        return booster.predict(X)
    raise ValueError(f"Unknown model_type: {model_type}")


def evaluate(
    model_type: str,
    X_test: np.ndarray,
    y_test: np.ndarray,
    feature_names: list[str],
    test_df: pd.DataFrame,
) -> dict:
    """Run full evaluation and return results dict."""
    # Load calibrator
    cal_path = ARTIFACT_DIR / f"calibrator_{model_type}.pkl"
    if not cal_path.exists():
        cal_path = ARTIFACT_DIR / "calibrator.pkl"
    calibrator = joblib.load(cal_path)

    # Raw and calibrated predictions
    raw_probs = _raw_predict(model_type, X_test)
    cal_probs = calibrator.predict(raw_probs)

    # Prior baseline
    prior_idx = feature_names.index("pregame_logit")
    prior_logits = X_test[:, prior_idx]
    prior_probs = 1 / (1 + np.exp(-prior_logits))

    # ── Core metrics ──────────────────────────────────────────────────────────
    model_ll = log_loss(y_test, cal_probs)
    model_bs = brier_score_loss(y_test, cal_probs)
    prior_ll = log_loss(y_test, prior_probs)
    prior_bs = brier_score_loss(y_test, prior_probs)

    logger.info("=== HOLDOUT TEST EVALUATION (%s, calibrated) ===", model_type.upper())
    logger.info("Prior-only:  log_loss=%.6f  brier=%.6f", prior_ll, prior_bs)
    logger.info("Model:       log_loss=%.6f  brier=%.6f", model_ll, model_bs)
    logger.info("Improvement: log_loss=+%.6f  brier=+%.6f",
                prior_ll - model_ll, prior_bs - model_bs)

    # ── Reliability curve ─────────────────────────────────────────────────────
    frac_pos, mean_pred = calibration_curve(y_test, cal_probs, n_bins=10, strategy="uniform")
    reliability = {
        "mean_predicted": mean_pred.tolist(),
        "fraction_positive": frac_pos.tolist(),
        "max_error": float(np.abs(frac_pos - mean_pred).max()),
        "mean_error": float(np.abs(frac_pos - mean_pred).mean()),
    }

    # ── Edge bucket analysis ──────────────────────────────────────────────────
    # "Edge" from model perspective: how far from 0.5
    edge_buckets = []
    test_df_copy = test_df.copy()
    test_df_copy["cal_prob"] = cal_probs
    test_df_copy["y"] = y_test
    test_df_copy["abs_edge"] = np.abs(cal_probs - 0.5)

    bucket_edges = [0.0, 0.03, 0.05, 0.08, 0.12, 0.20, 1.0]
    for lo, hi in zip(bucket_edges[:-1], bucket_edges[1:]):
        mask = (test_df_copy["abs_edge"] >= lo) & (test_df_copy["abs_edge"] < hi)
        sub = test_df_copy[mask]
        if len(sub) == 0:
            continue
        # When model says YES (cal_prob > 0.5), does it win?
        yes_mask = sub["cal_prob"] > 0.5
        no_mask = sub["cal_prob"] <= 0.5
        yes_acc = sub[yes_mask]["y"].mean() if yes_mask.sum() > 0 else float("nan")
        no_acc = (1 - sub[no_mask]["y"]).mean() if no_mask.sum() > 0 else float("nan")
        edge_buckets.append({
            "edge_lo": lo,
            "edge_hi": hi,
            "n": int(len(sub)),
            "mean_yes_accuracy": float(yes_acc) if not np.isnan(yes_acc) else None,
            "mean_no_accuracy": float(no_acc) if not np.isnan(no_acc) else None,
        })
        logger.info("  Edge [%.2f, %.2f): n=%d  yes_acc=%.4f  no_acc=%.4f",
                    lo, hi, len(sub),
                    yes_acc if not np.isnan(yes_acc) else -1,
                    no_acc if not np.isnan(no_acc) else -1)

    # ── Per-inning breakdown ──────────────────────────────────────────────────
    inning_breakdown = []
    if "inning" in test_df_copy.columns:
        for inning_grp, grp in test_df_copy.groupby("inning"):
            grp_probs = grp["cal_prob"].values
            grp_y = grp["y"].values
            if len(grp) < 50:
                continue
            grp_ll = log_loss(grp_y, grp_probs)
            grp_bs = brier_score_loss(grp_y, grp_probs)
            inning_breakdown.append({
                "inning": int(inning_grp),
                "n": int(len(grp)),
                "log_loss": float(grp_ll),
                "brier": float(grp_bs),
            })

    # ── Promotion check ───────────────────────────────────────────────────────
    beats_prior_ll = model_ll < prior_ll
    beats_prior_bs = model_bs < prior_bs
    reliability_acceptable = reliability["max_error"] < 0.08
    # Check 55%-70% range specifically (tradable zone)
    tradable_mask = (cal_probs > 0.55) & (cal_probs < 0.70)
    if tradable_mask.sum() > 100:
        fp_t, mp_t = calibration_curve(y_test[tradable_mask], cal_probs[tradable_mask],
                                       n_bins=5, strategy="quantile")
        tradable_cal_error = float(np.abs(fp_t - mp_t).max())
    else:
        tradable_cal_error = 0.0

    no_overconfidence = tradable_cal_error < 0.06

    promoted = beats_prior_ll and beats_prior_bs and reliability_acceptable and no_overconfidence

    logger.info("=== PROMOTION CHECK ===")
    logger.info("  beats_prior_log_loss: %s", beats_prior_ll)
    logger.info("  beats_prior_brier:    %s", beats_prior_bs)
    logger.info("  reliability_acceptable (max_err<0.08): %s (max=%.4f)", reliability_acceptable, reliability["max_error"])
    logger.info("  no_overconfidence_55_70 (err<0.06): %s (max=%.4f)", no_overconfidence, tradable_cal_error)
    logger.info("  PROMOTED: %s", promoted)

    return {
        "model_type": model_type,
        "test_log_loss": model_ll,
        "test_brier": model_bs,
        "prior_log_loss": prior_ll,
        "prior_brier": prior_bs,
        "improvement_log_loss": prior_ll - model_ll,
        "improvement_brier": prior_bs - model_bs,
        "reliability": reliability,
        "tradable_cal_error": tradable_cal_error,
        "edge_buckets": edge_buckets,
        "inning_breakdown": inning_breakdown,
        "promotion_check": {
            "beats_prior_log_loss": bool(beats_prior_ll),
            "beats_prior_brier": bool(beats_prior_bs),
            "reliability_acceptable": bool(reliability_acceptable),
            "no_overconfidence_tradable": bool(no_overconfidence),
            "promoted": bool(promoted),
        },
    }


def save_report(results: dict) -> Path:
    """Generate markdown model report."""
    r = results
    pc = r["promotion_check"]
    status = "PROMOTED" if pc["promoted"] else "NOT PROMOTED"

    lines = [
        f"# MLB Win Probability Model Report",
        f"",
        f"**Model:** `{r['model_type']}`  **Status:** {status}",
        f"",
        f"## Core Metrics (Test Set 2025)",
        f"",
        f"| Metric | Prior-only | Model | Improvement |",
        f"|--------|-----------|-------|-------------|",
        f"| Log Loss | {r['prior_log_loss']:.6f} | {r['test_log_loss']:.6f} | +{r['improvement_log_loss']:.6f} |",
        f"| Brier Score | {r['prior_brier']:.6f} | {r['test_brier']:.6f} | +{r['improvement_brier']:.6f} |",
        f"",
        f"## Calibration",
        f"",
        f"- Max calibration error: `{r['reliability']['max_error']:.4f}`",
        f"- Mean calibration error: `{r['reliability']['mean_error']:.4f}`",
        f"- Tradable zone (55-70%) max error: `{r['tradable_cal_error']:.4f}`",
        f"",
        f"## Promotion Check",
        f"",
        f"| Check | Pass |",
        f"|-------|------|",
    ]
    for check_name, check_val in pc.items():
        if check_name != "promoted":
            lines.append(f"| {check_name} | {'PASS' if check_val else 'FAIL'} |")
    lines += [
        f"",
        f"**Final verdict: {status}**",
        f"",
        f"## Edge Bucket Analysis",
        f"",
        f"| Edge Range | N | YES accuracy | NO accuracy |",
        f"|-----------|---|-------------|------------|",
    ]
    for b in r["edge_buckets"]:
        yes_a = f"{b['mean_yes_accuracy']:.4f}" if b["mean_yes_accuracy"] is not None else "—"
        no_a = f"{b['mean_no_accuracy']:.4f}" if b["mean_no_accuracy"] is not None else "—"
        lines.append(f"| [{b['edge_lo']:.2f}, {b['edge_hi']:.2f}) | {b['n']} | {yes_a} | {no_a} |")

    report_path = ARTIFACT_DIR / "model_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    logger.info("Saved report: %s", report_path)
    return report_path


def main():
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Evaluate calibrated model on holdout")
    parser.add_argument("--model", choices=["logistic", "lgbm"], default="lgbm")
    parser.add_argument("--test-seasons", nargs="+", type=int, default=[2025])
    args = parser.parse_args()

    from data.feature_store import load_feature_store, FEATURE_COLUMNS, TARGET_COLUMN

    features = load_feature_store()
    test_df = features[features["season"].isin(args.test_seasons)].reset_index(drop=True)

    if test_df.empty:
        logger.error("No test data for seasons %s. Run data pipeline first.", args.test_seasons)
        return

    logger.info("Test set: %d rows", len(test_df))
    X_test = test_df[FEATURE_COLUMNS].values
    y_test = test_df[TARGET_COLUMN].values

    results = evaluate(args.model, X_test, y_test, FEATURE_COLUMNS, test_df)

    # Save full results JSON
    results_path = ARTIFACT_DIR / "evaluation_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info("Saved evaluation results: %s", results_path)

    save_report(results)


if __name__ == "__main__":
    main()
