"""
scripts/retrain_after_features.py

End-to-end retrain after phase-1 features land:
  1. Regenerate features_all.parquet (calls feature_store.main())
  2. Train LightGBM (calls models.train_lightgbm.main())
  3. Calibrate on 2024 (calls models.calibrate_model.main())
  4. Evaluate on 2025 (calls models.evaluate_model.main())
  5. Run audit (models.audit_features.write_audit_report)
  6. If verdict == PROMOTE, archive old artifacts and export new
  7. Else: leave existing artifacts in place, log report path
"""
from __future__ import annotations
import json
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

# Ensure project root is on sys.path when invoked as `python scripts/retrain_after_features.py`
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logger = logging.getLogger(__name__)

ARTIFACT_DIR = Path("artifacts")
ARCHIVE_DIR = ARTIFACT_DIR / "archive"


def archive_existing() -> Path | None:
    """Copy current artifacts to archive/<timestamp>/. Returns archive path or None."""
    files = [p for p in ARTIFACT_DIR.iterdir() if p.is_file()]
    if not files:
        return None
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = ARCHIVE_DIR / ts
    dest.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy2(f, dest / f.name)
    logger.info("Archived %d artifact files to %s", len(files), dest)
    return dest


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    # 1. regenerate features
    from data.feature_store import main as build_features
    logger.info("[1/6] regenerating features_all.parquet...")
    build_features()

    # 2. train
    from models.train_lightgbm import main as train_main
    logger.info("[2/6] training LightGBM...")
    train_main()

    # 3. calibrate
    from models.calibrate_model import main as cal_main
    logger.info("[3/6] calibrating on 2024...")
    cal_main()

    # 4. evaluate
    from models.evaluate_model import main as eval_main
    logger.info("[4/6] evaluating on 2025...")
    eval_main()

    # 5. audit all three phases together (phase-1 + phase-2 + phase-3)
    from models.audit_features import (
        write_audit_report, PHASE1_NEW_FEATURES, PHASE2_NEW_FEATURES,
        PHASE3_NEW_FEATURES, PHASE4_NEW_FEATURES,
    )
    logger.info("[5/6] running audit across all new feature groups...")
    features = pd.read_parquet("data/features/features_all.parquet")
    test_mask = features["season"] == 2025
    all_new_features = PHASE1_NEW_FEATURES + PHASE2_NEW_FEATURES + PHASE3_NEW_FEATURES + PHASE4_NEW_FEATURES
    # Exclude non-numeric snapshot columns that feature_store carries through but
    # aren't fed to the model (team abbrevs, lineup lists, pitcher handedness).
    non_feature_cols = [
        "season", "home_won_final", "p_home_pred", "market_yes_cost",
        "game_id", "date", "home_team", "away_team",
        "home_pitcher_id", "away_pitcher_id", "park_id",
        "batter_id", "batter_stand", "home_pitcher_p_throws", "away_pitcher_p_throws",
        "home_lineup_ids", "away_lineup_ids", "current_lineup_position",
    ]
    baseline_cols = [c for c in features.columns
                     if c not in (all_new_features + non_feature_cols)]
    if "p_home_pred" not in features.columns:
        import joblib
        # Use the freshly-trained LightGBM model (40-col). winprob_model.pkl may be
        # a stale 30-col model from a prior promotion — don't load that here.
        model = joblib.load(ARTIFACT_DIR / "lgbm_model.pkl")
        cal = joblib.load(ARTIFACT_DIR / "calibrator_lgbm.pkl")
        # LightGBM was trained on FEATURE_COLUMNS directly — use that order
        from data.feature_store import FEATURE_COLUMNS
        raw = model.predict(features[FEATURE_COLUMNS])
        features["p_home_pred"] = cal.predict(raw)
    if "market_yes_cost" not in features.columns:
        features["market_yes_cost"] = 0.5

    report = write_audit_report(
        features_df=features, target_col="home_won_final",
        pred_col="p_home_pred", market_cost_yes_col="market_yes_cost",
        baseline_cols=baseline_cols, new_cols=all_new_features,
        test_mask=test_mask,
    )

    # 6. promote or reject
    logger.info("[6/6] verdict: %s", report["verdict"])
    if report["verdict"] in ("PROMOTE", "PROMOTE_MARGINAL"):
        archive_existing()
        from models.export_artifacts import main as export_main
        export_main()
        if report["verdict"] == "PROMOTE_MARGINAL":
            logger.warning("MARGINAL promotion — ablation delta=%.4f (floor=%.4f); shipped "
                           "because SHAP confirms features carry signal. Review audit_report.json.",
                           report["ablation"]["delta"], -0.003)
        else:
            logger.info("Promoted new artifacts.")
        return 0
    elif report["verdict"] == "PROMOTE_WITH_CAVEAT":
        logger.warning("Caveat verdict — review audit_report.json before manual promote.")
        return 2
    else:
        logger.error("REJECTED — new features did not pass ablation. Old artifacts kept.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
