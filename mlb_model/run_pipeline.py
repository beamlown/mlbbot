"""
run_pipeline.py — Orchestrate the full offline training pipeline

Runs all steps in sequence:
  1. Download historical data (Retrosheet game logs + Statcast)
  2. Build Elo pregame prior table
  3. Build game-state snapshots
  4. Engineer features
  5. Train logistic baseline
  6. Train LightGBM challenger
  7. Calibrate best model
  8. Evaluate on holdout
  9. Export artifacts

Usage:
    python run_pipeline.py --seasons 2018 2019 2020 2021 2022 2023 2024 2025
    python run_pipeline.py --skip-download --model lgbm   # if data already cached

This script is meant for offline training. It is NOT the live trading loop.
"""
from __future__ import annotations

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/pipeline.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("run_pipeline")


def main():
    import pathlib
    pathlib.Path("logs").mkdir(exist_ok=True)

    parser = argparse.ArgumentParser(description="Run full MLB model training pipeline")
    parser.add_argument("--seasons", nargs="+", type=int,
                        default=list(range(2018, 2026)),
                        help="Seasons to include in pipeline")
    parser.add_argument("--model", choices=["logistic", "lgbm", "both"], default="both",
                        help="Which model(s) to train")
    parser.add_argument("--skip-download", action="store_true",
                        help="Skip data download (use cached parquet files)")
    parser.add_argument("--skip-retrosheet", action="store_true",
                        help="Skip Retrosheet download (use cached Elo table if it exists)")
    parser.add_argument("--force-download", action="store_true",
                        help="Re-download even if cached")
    parser.add_argument("--skip-eval", action="store_true",
                        help="Skip evaluation (run training only)")
    parser.add_argument("--force-rebuild-snapshots", action="store_true",
                        help="Rebuild snapshot parquet files even if they already exist")
    parser.add_argument("--skip-to-features", action="store_true",
                        help="Skip download, Elo build, and snapshot build — go straight to "
                             "feature engineering and training (requires all parquet files cached)")
    args = parser.parse_args()

    all_seasons = args.seasons
    # Standard split
    train_seasons = [s for s in all_seasons if s <= 2022]
    val_seasons = [s for s in all_seasons if s == 2023]
    cal_seasons = [s for s in all_seasons if s == 2024]
    test_seasons = [s for s in all_seasons if s == 2025]

    logger.info("Pipeline starting — seasons: %s", all_seasons)
    logger.info("  Train: %s | Val: %s | Cal: %s | Test: %s",
                train_seasons, val_seasons, cal_seasons, test_seasons)

    # ── Pipeline state tracking (for end-of-run summary) ─────────────────────
    _summary: dict = {
        "elo_status": "not_run",       # "real" | "degraded" | "not_run"
        "snapshots_reused": [],
        "snapshots_rebuilt": [],
        "snapshots_skipped": [],       # no statcast data
        "feature_rows": 0,
        "trained": [],
        "calibrated": [],
        "exported": False,
        "promoted": None,
    }

    # ── Step 1: Data download ─────────────────────────────────────────────────
    if not args.skip_download and not args.skip_to_features:
        logger.info("=== Step 1: Data download ===")
        from data.retrosheet_ingest import load_statcast_season, fetch_retrosheet_game_log
        for year in all_seasons:
            load_statcast_season(year, force=args.force_download)
    elif args.skip_to_features:
        logger.info("=== Step 1: Skipped (--skip-to-features) ===")

    # ── Step 2: Elo prior ─────────────────────────────────────────────────────
    if not args.skip_retrosheet and not args.skip_to_features:
        logger.info("=== Step 2: Elo pregame prior ===")
        from data.retrosheet_ingest import load_retrosheet_seasons
        from data.pregame_prior_builder import build_elo_table, save_elo_table

        # Use extended history for better Elo convergence
        elo_seasons = list(range(2010, max(all_seasons) + 1))
        game_logs = load_retrosheet_seasons(elo_seasons)
        if game_logs.empty:
            logger.error(
                "╔══════════════════════════════════════════════════════════════╗\n"
                "║  ELO TABLE BUILD FAILED — NO RETROSHEET DATA                ║\n"
                "║  Pipeline will continue with pregame_win_prob = 0.54        ║\n"
                "║  (flat default) for ALL games. This is a DEGRADED run.      ║\n"
                "║  elo_diff_norm and pregame_logit features will be wrong.    ║\n"
                "║  DO NOT use a model trained in this state for production.   ║\n"
                "╚══════════════════════════════════════════════════════════════╝"
            )
            _summary["elo_status"] = "degraded"
        else:
            elo_df = build_elo_table(game_logs, elo_seasons)
            save_elo_table(elo_df)
            logger.info("Elo table built: %d rows", len(elo_df))
            _summary["elo_status"] = "real"
    elif args.skip_to_features:
        logger.info("=== Step 2: Skipped (--skip-to-features) ===")
        _summary["elo_status"] = "not_run"
    else:
        # --skip-retrosheet passed explicitly
        _summary["elo_status"] = "not_run"

    # ── Step 3: Snapshots ─────────────────────────────────────────────────────
    import os as _os
    import pandas as pd
    from pathlib import Path as _Path

    _FEATURE_DIR = _Path(_os.getenv("FEATURE_DIR", "data/features"))

    if not args.skip_to_features:
        logger.info("=== Step 3: Game-state snapshots ===")
        from data.state_snapshot_builder import build_snapshots_for_season, save_snapshots
        from data.pregame_prior_builder import load_elo_table
        from data.retrosheet_ingest import load_statcast_season

        try:
            elo_table = load_elo_table()
        except FileNotFoundError:
            if _summary["elo_status"] != "degraded":
                logger.warning("No Elo table — using default prior")
                _summary["elo_status"] = "degraded"
            elo_table = pd.DataFrame()

        for year in all_seasons:
            snap_path = _FEATURE_DIR / f"snapshots_{year}.parquet"
            if snap_path.exists() and not args.force_rebuild_snapshots:
                existing_rows = len(pd.read_parquet(snap_path))
                logger.info(
                    "Snapshot reuse: %s  (%d rows) — pass --force-rebuild-snapshots to rebuild",
                    snap_path, existing_rows,
                )
                _summary["snapshots_reused"].append(year)
                continue

            statcast = load_statcast_season(year)
            if statcast.empty:
                logger.warning("No statcast data for %d — skipping", year)
                _summary["snapshots_skipped"].append(year)
                continue

            action = "Rebuilding" if snap_path.exists() else "Building"
            logger.info("%s snapshots for %d ...", action, year)
            snaps = build_snapshots_for_season(statcast, elo_table, year)
            if not snaps.empty:
                save_snapshots(snaps, year)
                _summary["snapshots_rebuilt"].append(year)
    else:
        logger.info("=== Step 3: Skipped (--skip-to-features) ===")
        # Record which snapshots exist so the summary is informative
        for year in all_seasons:
            snap_path = _FEATURE_DIR / f"snapshots_{year}.parquet"
            if snap_path.exists():
                _summary["snapshots_reused"].append(year)
            else:
                _summary["snapshots_skipped"].append(year)

    # ── Step 4: Feature engineering ───────────────────────────────────────────
    logger.info("=== Step 4: Feature engineering ===")
    from data.feature_store import build_feature_store
    features = build_feature_store(all_seasons)
    _summary["feature_rows"] = len(features)
    logger.info("Feature store: %d rows", len(features))

    # ── Step 5 & 6: Model training ────────────────────────────────────────────
    import numpy as np
    from data.feature_store import FEATURE_COLUMNS, TARGET_COLUMN

    train_df = features[features["season"].isin(train_seasons)] if train_seasons else features
    val_df = features[features["season"].isin(val_seasons)] if val_seasons else features.iloc[:0]

    X_train = train_df[FEATURE_COLUMNS].values
    y_train = train_df[TARGET_COLUMN].values
    X_val = val_df[FEATURE_COLUMNS].values if len(val_df) > 0 else X_train[:0]
    y_val = val_df[TARGET_COLUMN].values if len(val_df) > 0 else y_train[:0]

    if args.model in ("logistic", "both"):
        logger.info("=== Step 5: Logistic baseline ===")
        from models.train_logistic_baseline import train_logistic
        import joblib, pathlib
        pathlib.Path("artifacts").mkdir(exist_ok=True)
        pipe, best_c, val_loss = train_logistic(X_train, y_train, X_val, y_val, FEATURE_COLUMNS)
        joblib.dump(pipe, "artifacts/logistic_baseline.pkl")
        logger.info("Logistic trained: C=%.4f val_loss=%.6f", best_c, val_loss)
        _summary["trained"].append("logistic")

    if args.model in ("lgbm", "both"):
        logger.info("=== Step 6: LightGBM challenger ===")
        from models.train_lightgbm import train_lightgbm
        import joblib
        booster = train_lightgbm(X_train, y_train, X_val, y_val, FEATURE_COLUMNS)
        joblib.dump(booster, "artifacts/lgbm_model.pkl")
        logger.info("LightGBM trained: %d trees", booster.num_trees())
        import json as _json
        with open("artifacts/lgbm_model_meta.json", "w") as _f:
            _json.dump({
                "model_type": "lightgbm",
                "best_n_estimators": booster.num_trees(),
                "train_seasons": train_seasons,
                "val_seasons": val_seasons,
            }, _f, indent=2)
        _summary["trained"].append("lgbm")

    # ── Step 7: Calibration ───────────────────────────────────────────────────
    logger.info("=== Step 7: Calibration ===")
    if cal_seasons:
        cal_df = features[features["season"].isin(cal_seasons)]
        from models.calibrate_model import calibrate_and_compare

        for mtype in (["lgbm"] if args.model == "lgbm"
                      else ["logistic"] if args.model == "logistic"
                      else ["logistic", "lgbm"]):
            try:
                from models.calibrate_model import _raw_predict
                import numpy as np
                raw_cal = _raw_predict(mtype, cal_df[FEATURE_COLUMNS].values)
                cal, method = calibrate_and_compare(
                    raw_cal, cal_df[TARGET_COLUMN].values,
                )
                import joblib
                joblib.dump(cal, f"artifacts/calibrator_{mtype}.pkl")
                logger.info("%s calibrated with method=%s", mtype, method)
                _summary["calibrated"].append(mtype)
            except Exception as e:
                logger.warning("Calibration failed for %s: %s", mtype, e)
    else:
        logger.warning("No calibration seasons — skipping calibration step")

    # ── Step 8: Evaluation ────────────────────────────────────────────────────
    if not args.skip_eval and test_seasons:
        logger.info("=== Step 8: Evaluation on holdout ===")
        from models.evaluate_model import evaluate, save_report as save_eval_report

        test_df = features[features["season"].isin(test_seasons)]
        best_model = "lgbm" if args.model != "logistic" else "logistic"
        try:
            results = evaluate(
                best_model,
                test_df[FEATURE_COLUMNS].values,
                test_df[TARGET_COLUMN].values,
                FEATURE_COLUMNS,
                test_df,
            )
            # Persist JSON first — export_artifacts depends on this file.
            # Do this before save_eval_report so a report-formatting failure
            # cannot block export.
            import json as _json2
            _eval_path = pathlib.Path("artifacts") / "evaluation_results.json"
            _eval_path.parent.mkdir(exist_ok=True)
            with open(_eval_path, "w", encoding="utf-8") as _ef:
                _json2.dump(results, _ef, indent=2, default=str)
            promoted = results["promotion_check"]["promoted"]
            _summary["promoted"] = promoted
            logger.info("Holdout evaluation: promoted=%s", promoted)
            save_eval_report(results)
        except Exception as e:
            logger.warning("Evaluation failed: %s", e)
    else:
        logger.info("Skipping holdout evaluation (no 2025 data yet or --skip-eval)")

    # ── Step 9: Export ────────────────────────────────────────────────────────
    logger.info("=== Step 9: Export artifacts ===")
    best_model = "lgbm" if args.model != "logistic" else "logistic"
    try:
        from models.export_artifacts import export_artifacts
        manifest = export_artifacts(best_model, force_export=False)
        logger.info("Artifacts exported: version=%s", manifest["model_version"])
        _summary["exported"] = True
    except Exception as e:
        logger.warning("Artifact export failed: %s", e)

    # ── End-of-run summary ────────────────────────────────────────────────────
    _elo_label = {
        "real":     "REAL  (Elo table built from Retrosheet)",
        "degraded": "DEGRADED  *** pregame_win_prob = 0.54 flat for all games ***",
        "not_run":  "cached  (snapshots/features loaded from disk; prior run used real Elo)",
    }.get(_summary["elo_status"], _summary["elo_status"])

    _snap_total = (len(_summary["snapshots_reused"]) +
                   len(_summary["snapshots_rebuilt"]) +
                   len(_summary["snapshots_skipped"]))

    logger.info(
        "\n"
        "╔══════════════════════════════════════════════════════════════╗\n"
        "║              PIPELINE RUN SUMMARY                           ║\n"
        "╠══════════════════════════════════════════════════════════════╣\n"
        "║  Elo prior   : %-46s ║\n"
        "║  Snapshots   : %d total                                      ║\n"
        "║    reused    : %-46s ║\n"
        "║    rebuilt   : %-46s ║\n"
        "║    skipped   : %-46s ║\n"
        "║  Feature rows: %-46s ║\n"
        "║  Trained     : %-46s ║\n"
        "║  Calibrated  : %-46s ║\n"
        "║  Promoted    : %-46s ║\n"
        "║  Exported    : %-46s ║\n"
        "╚══════════════════════════════════════════════════════════════╝",
        _elo_label,
        _snap_total,
        str(_summary["snapshots_reused"]) if _summary["snapshots_reused"] else "none",
        str(_summary["snapshots_rebuilt"]) if _summary["snapshots_rebuilt"] else "none",
        str(_summary["snapshots_skipped"]) if _summary["snapshots_skipped"] else "none",
        str(_summary["feature_rows"]),
        str(_summary["trained"]) if _summary["trained"] else "none",
        str(_summary["calibrated"]) if _summary["calibrated"] else "none",
        str(_summary["promoted"]),
        str(_summary["exported"]),
    )

    if _summary["elo_status"] == "degraded":
        logger.error(
            "DEGRADED RUN: Elo table was not built. Model trained on flat priors. "
            "Do NOT export this artifact for production use."
        )

    logger.info("=== Pipeline complete ===")


if __name__ == "__main__":
    main()
