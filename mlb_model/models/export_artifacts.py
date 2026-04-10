"""
models/export_artifacts.py — Bundle model artifacts for deployment

Validates that all required artifacts exist and copies them to artifacts/
with a manifest file. The inference module expects exactly these paths.

Artifacts:
    artifacts/winprob_model.pkl     ← active model (logistic or lgbm)
    artifacts/calibrator.pkl        ← active calibrator
    artifacts/feature_schema.json   ← feature column list
    artifacts/model_report.md       ← evaluation report

Usage:
    python -m models.export_artifacts --model lgbm
    python -m models.export_artifacts --model logistic
"""
from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", "artifacts"))


def export_artifacts(model_type: str, force_export: bool = False) -> dict:
    """
    Copy the active model to winprob_model.pkl and validate all required files exist.
    Returns manifest dict.
    """
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    # Source model file
    if model_type == "logistic":
        model_src = ARTIFACT_DIR / "logistic_baseline.pkl"
        meta_src = ARTIFACT_DIR / "logistic_baseline_meta.json"
    elif model_type == "lgbm":
        model_src = ARTIFACT_DIR / "lgbm_model.pkl"
        meta_src = ARTIFACT_DIR / "lgbm_model_meta.json"
    else:
        raise ValueError(f"Unknown model_type: {model_type}")

    calibrator_src = ARTIFACT_DIR / f"calibrator_{model_type}.pkl"

    # Check all source files exist
    required_sources = [model_src, meta_src, calibrator_src]
    for src in required_sources:
        if not src.exists():
            raise FileNotFoundError(f"Required artifact not found: {src}")

    # Check feature schema
    schema_path = ARTIFACT_DIR / "feature_schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"Feature schema not found: {schema_path}")

    # Check evaluation report
    report_path = ARTIFACT_DIR / "model_report.md"
    if not report_path.exists():
        raise FileNotFoundError(f"Model report not found: {report_path}. Run evaluate_model first.")

    # Check promotion status from evaluation results
    eval_path = ARTIFACT_DIR / "evaluation_results.json"
    if eval_path.exists():
        with open(eval_path) as f:
            eval_results = json.load(f)
        promoted = eval_results.get("promotion_check", {}).get("promoted", False)
        if not promoted and not force_export:
            raise RuntimeError(
                "Model did NOT pass all promotion checks — export blocked.\n"
                "Review artifacts/model_report.md for the failing checks.\n"
                "To override (not recommended), pass force_export=True or use --force-export."
            )
        if not promoted and force_export:
            logger.warning(
                "FORCE EXPORT: model failed promotion checks but --force-export was set. "
                "Review model_report.md before using this artifact in production."
            )
    else:
        if not force_export:
            raise RuntimeError(
                "No evaluation results found — export blocked.\n"
                "Run evaluate_model first, or pass --force-export to override."
            )
        logger.warning("No evaluation results found. Proceeding due to --force-export.")
        eval_results = {}

    # Copy active artifacts
    dest_model = ARTIFACT_DIR / "winprob_model.pkl"
    dest_calibrator = ARTIFACT_DIR / "calibrator.pkl"

    shutil.copy2(model_src, dest_model)
    shutil.copy2(calibrator_src, dest_calibrator)
    logger.info("Exported model: %s → %s", model_src.name, dest_model.name)
    logger.info("Exported calibrator: %s → %s", calibrator_src.name, dest_calibrator.name)

    # Read schema
    with open(schema_path) as f:
        schema = json.load(f)

    # Write deployment manifest
    manifest = {
        "model_type": model_type,
        "model_version": f"mlb_winprob_v1_{model_type}",
        "model_file": str(dest_model),
        "calibrator_file": str(dest_calibrator),
        "schema_file": str(schema_path),
        "feature_columns": schema["feature_columns"],
        "n_features": schema["n_features"],
        "export_ts": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "promotion_passed": eval_results.get("promotion_check", {}).get("promoted", None),
        "test_log_loss": eval_results.get("test_log_loss"),
        "test_brier": eval_results.get("test_brier"),
    }

    manifest_path = ARTIFACT_DIR / "deployment_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    logger.info("Saved deployment manifest: %s", manifest_path)

    logger.info("=== Export complete ===")
    logger.info("  Model version: %s", manifest["model_version"])
    logger.info("  Features: %d", manifest["n_features"])
    if manifest["promotion_passed"] is not None:
        logger.info("  Promoted: %s", manifest["promotion_passed"])

    return manifest


def main():
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Export model artifacts for deployment")
    parser.add_argument("--model", choices=["logistic", "lgbm"], default="lgbm")
    parser.add_argument(
        "--force-export",
        action="store_true",
        help="Export even if promotion check failed. Use only for debugging — "
             "do not deploy artifacts exported with this flag to production.",
    )
    args = parser.parse_args()
    export_artifacts(args.model, force_export=args.force_export)


if __name__ == "__main__":
    main()
