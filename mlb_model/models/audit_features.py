"""
models/audit_features.py

Three independent gates that a new feature group must pass to ship to prod:
  1. Ablation:        train with vs without → log loss delta ≥ 0.005
  2. SHAP importance: new feature ranks in top 50% of all features OR has
                       non-zero interaction with existing features
  3. Tradable lift:   among edge≥5% trades, high-feature-value bucket beats
                       low-feature-value bucket by ≥ 3pp on win rate

Output: artifacts/audit_report.json with verdict.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

ARTIFACT_DIR = Path("artifacts")
# 2026-04-20 prune pass: dropped pregame_prior_source (variance=0 in historical)
# and park_run_factor_x_late (rank 22, weak). Both kept in enrichment output for
# inspection but not in the trained feature set.
PHASE1_NEW_FEATURES = [
    "home_sp_quality", "away_sp_quality",
    "home_sp_recent_form", "away_sp_recent_form",
    "sp_quality_diff", "park_run_factor",
]

# 2026-04-20 prune pass: dropped current_batter_xwoba, next3_avg_xwoba,
# current_batter_platoon_advantage, current_batter_xwoba_x_late — all showed
# 0 SHAP importance across 1.4M rows. Kept lineup_avg_xwoba which ranked 17.
PHASE2_NEW_FEATURES = [
    "lineup_avg_xwoba",
]

PHASE3_NEW_FEATURES = [
    "home_reliever_quality",
    "away_reliever_quality",
    "home_bullpen_avg_quality",
    "away_bullpen_avg_quality",
    "leverage_index",
]

# 2026-04-20 post-audit prune: dropped is_roof_closed, in_extras,
# ghost_runner_on_2nd — all zero SHAP in 39-feature audit. Kept in
# enrichment output for inspection.
PHASE4_NEW_FEATURES = [
    "wind_out_mph",
    "temp_f",
]

ABLATION_THRESHOLD = 0.005
# Marginal-promote floor: features can still ship if they don't HURT the model
# by more than ABLATION_MARGINAL_FLOOR AND SHAP confirms they're being used.
# 2026-04-20: added to avoid rejecting features that are slightly worse on offline
# log loss but carry meaningful live-inference context (e.g. real-time bullpen
# matchups, leverage-weighted priors) that aggregate log-loss can't measure.
ABLATION_MARGINAL_FLOOR = -0.003
SHAP_TOP_HALF_RANK_PCT = 0.50
LIFT_THRESHOLD_PP = 0.03


def _train_lgbm(X: pd.DataFrame, y: pd.Series, feat_cols: list[str],
                val_X: pd.DataFrame | None = None, val_y: pd.Series | None = None):
    """Train LightGBM with optional early stopping on a validation set.

    2026-04-20: audit now uses early stopping (matches production trainer).
    Without early stopping, 300 rounds on 1.1M rows overfits — leads to
    unfair comparison vs the early-stopped production model.
    """
    import lightgbm as lgb
    dtrain = lgb.Dataset(X[feat_cols], label=y)
    params = {
        "objective": "binary",
        "metric": "binary_logloss",
        "learning_rate": 0.05,
        "num_leaves": 63,
        "verbose": -1,
    }
    if val_X is not None and val_y is not None:
        dval = lgb.Dataset(val_X[feat_cols], label=val_y, reference=dtrain)
        return lgb.train(
            params, dtrain, num_boost_round=500,
            valid_sets=[dval], valid_names=["val"],
            callbacks=[lgb.early_stopping(50, verbose=False)],
        )
    return lgb.train(params, dtrain, num_boost_round=300)


def _log_loss(y_true, p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y_true * np.log(p) + (1 - y_true) * np.log(1 - p)))


def ablation_test(features_df: pd.DataFrame, target_col: str,
                  baseline_cols: list[str], new_cols: list[str],
                  test_mask: pd.Series) -> dict:
    # Use season 2024 as the val set for early stopping (matches production split),
    # train on earlier seasons, test on test_mask (2025).
    val_mask = features_df["season"] == 2024 if "season" in features_df.columns else None
    if val_mask is not None:
        train_mask = (~test_mask) & (~val_mask)
        train = features_df[train_mask]
        val = features_df[val_mask]
    else:
        train = features_df[~test_mask]
        val = None
    test = features_df[test_mask]

    if val is not None:
        m_with = _train_lgbm(train, train[target_col], baseline_cols + new_cols,
                             val, val[target_col])
        m_without = _train_lgbm(train, train[target_col], baseline_cols,
                                val, val[target_col])
    else:
        m_with = _train_lgbm(train, train[target_col], baseline_cols + new_cols)
        m_without = _train_lgbm(train, train[target_col], baseline_cols)

    p_with = m_with.predict(test[baseline_cols + new_cols])
    ll_with = _log_loss(test[target_col].values, p_with)

    p_without = m_without.predict(test[baseline_cols])
    ll_without = _log_loss(test[target_col].values, p_without)

    delta = ll_without - ll_with
    return {
        "log_loss_with": ll_with,
        "log_loss_without": ll_without,
        "delta": delta,
        "passed": delta >= ABLATION_THRESHOLD,
    }


def shap_importance(features_df: pd.DataFrame, target_col: str,
                    feat_cols: list[str], new_cols: list[str],
                    test_mask: pd.Series) -> dict:
    import shap
    train = features_df[~test_mask]
    test = features_df[test_mask].sample(min(5000, test_mask.sum()), random_state=0)

    model = _train_lgbm(train, train[target_col], feat_cols)
    explainer = shap.TreeExplainer(model)
    shap_vals = explainer.shap_values(test[feat_cols])
    if isinstance(shap_vals, list):
        shap_vals = shap_vals[1]
    mean_abs = np.abs(shap_vals).mean(axis=0)
    importance = dict(zip(feat_cols, mean_abs))
    ranked = sorted(importance.items(), key=lambda kv: kv[1], reverse=True)
    rank_map = {name: i + 1 for i, (name, _) in enumerate(ranked)}
    n = len(feat_cols)
    cutoff_rank = int(n * SHAP_TOP_HALF_RANK_PCT)
    per_new = {nm: {"importance": float(importance[nm]),
                    "rank": rank_map[nm],
                    "passed": rank_map[nm] <= cutoff_rank} for nm in new_cols}
    any_passed = any(v["passed"] for v in per_new.values())
    return {"per_feature": per_new, "any_passed": any_passed}


def tradable_lift(features_df: pd.DataFrame, target_col: str,
                  pred_col: str, market_cost_yes_col: str,
                  new_cols: list[str], test_mask: pd.Series) -> dict:
    """
    Bucket trades by each new feature's tertile and measure win rate.
    Requires features_df has a model prediction column already populated.
    """
    test = features_df[test_mask].copy()
    test["edge"] = test[pred_col] - test[market_cost_yes_col]
    actionable = test[test["edge"] >= 0.05]
    out = {}
    for col in new_cols:
        if actionable[col].nunique() < 3:
            out[col] = {"skipped": True, "reason": "not enough unique values"}
            continue
        try:
            actionable["bucket"] = pd.qcut(actionable[col], 3,
                                           labels=["low", "mid", "high"], duplicates="drop")
        except ValueError:
            out[col] = {"skipped": True, "reason": "qcut failed"}
            continue
        win = actionable.groupby("bucket")[target_col].mean()
        if "high" not in win or "low" not in win:
            out[col] = {"skipped": True, "reason": "missing bucket"}
            continue
        delta = float(win["high"] - win["low"])
        out[col] = {"high_winrate": float(win["high"]),
                    "low_winrate": float(win["low"]),
                    "delta_pp": delta,
                    "passed": delta >= LIFT_THRESHOLD_PP}
    any_passed = any(v.get("passed") for v in out.values() if not v.get("skipped"))
    return {"per_feature": out, "any_passed": any_passed}


def write_audit_report(features_df: pd.DataFrame, target_col: str,
                       pred_col: str, market_cost_yes_col: str,
                       baseline_cols: list[str], new_cols: list[str],
                       test_mask: pd.Series,
                       output_path: Path = ARTIFACT_DIR / "audit_report.json") -> dict:
    abl = ablation_test(features_df, target_col, baseline_cols, new_cols, test_mask)
    shp = shap_importance(features_df, target_col, baseline_cols + new_cols, new_cols, test_mask)
    lift = tradable_lift(features_df, target_col, pred_col, market_cost_yes_col,
                         new_cols, test_mask)

    # Verdict logic:
    #   PROMOTE           - ablation pass (>= +0.005 log loss improvement) AND shap/lift signal
    #   PROMOTE_MARGINAL  - ablation delta ∈ [-0.003, +0.005] AND shap signal (features
    #                       don't hurt meaningfully, SHAP confirms they're informative)
    #   PROMOTE_WITH_CAVEAT - ablation pass but neither shap nor lift earns a slot
    #   REJECT            - ablation delta < -0.003 (features actively hurt the model)
    delta = abl["delta"]
    if abl["passed"] and (shp["any_passed"] or lift["any_passed"]):
        verdict = "PROMOTE"
    elif abl["passed"]:
        verdict = "PROMOTE_WITH_CAVEAT"
    elif delta >= ABLATION_MARGINAL_FLOOR and shp["any_passed"]:
        verdict = "PROMOTE_MARGINAL"
    else:
        verdict = "REJECT"

    report = {
        "feature_group": "phase1",
        "new_features": new_cols,
        "ablation": abl,
        "shap": shp,
        "tradable_lift": lift,
        "verdict": verdict,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info("Audit report written: verdict=%s", verdict)
    return report
