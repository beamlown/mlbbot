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

    # ── PHASE-1 enrichment (added 2026-04-19) ────────────────────────────────
    # 2026-04-20: pruned park_run_factor_x_late (rank 22, weak) and
    # pregame_prior_source (variance=0 in historical data — all elo).
    "home_sp_quality",         # FIP- (100=avg, lower better)
    "away_sp_quality",
    "home_sp_recent_form",     # baseline_fip - trailing_30d_fip
    "away_sp_recent_form",
    "sp_quality_diff",         # away_sp_quality - home_sp_quality
    "park_run_factor",         # 3-yr rolling, 1.0=neutral

    # ── PHASE-2 enrichment (added 2026-04-19) ────────────────────────────────
    # 2026-04-20: pruned current_batter_xwoba, next3_avg_xwoba,
    # current_batter_platoon_advantage, current_batter_xwoba_x_late — all
    # showed 0 SHAP importance across 1.4M rows. Lineup-level signal is kept
    # via lineup_avg_xwoba. Enrichment still computes pruned features for
    # inspection; they just aren't fed to the trained model.
    "lineup_avg_xwoba",

    # ── PHASE-3 bullpen + leverage (added 2026-04-19) ────────────────────────
    "home_reliever_quality",
    "away_reliever_quality",
    "home_bullpen_avg_quality",
    "away_bullpen_avg_quality",
    "leverage_index",

    # ── PHASE-4 weather + extras (added 2026-04-20) ──────────────────────────
    # 2026-04-20 post-audit prune: dropped is_roof_closed (swamped by baseline's
    # is_indoor signal), in_extras and ghost_runner_on_2nd (both zero SHAP —
    # extras rows are <1% of sample, features never chosen for splits).
    # Enrichment still computes all 5 for inspection; only 2 are fed to model.
    "wind_out_mph",
    "temp_f",
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

    # IDs required by phase-1/2/3 enrichment joins (pitcher quality, park factors,
    # batter quality, reliever/bullpen quality). Forward from snapshot rows as-is.
    for id_col in [
        "home_pitcher_id", "away_pitcher_id",
        "batter_id", "batter_stand",
        "home_pitcher_p_throws", "away_pitcher_p_throws",
        "home_lineup_ids", "away_lineup_ids", "current_lineup_position",
        "park_id", "pregame_prior_source",
        "in_extras", "ghost_runner_on_2nd",
    ]:
        if id_col in df.columns:
            out[id_col] = df[id_col]

    # Validate no NaN in BASE feature columns (phase-1 cols added later in enrich step)
    base_cols = [c for c in FEATURE_COLUMNS if c not in (
        "home_sp_quality", "away_sp_quality",
        "home_sp_recent_form", "away_sp_recent_form",
        "sp_quality_diff", "park_run_factor",
        "park_run_factor_x_late", "pregame_prior_source",
        # phase-2
        "current_batter_xwoba", "next3_avg_xwoba", "lineup_avg_xwoba",
        "current_batter_platoon_advantage", "current_batter_xwoba_x_late",
        # phase-3
        "home_reliever_quality", "away_reliever_quality",
        "home_bullpen_avg_quality", "away_bullpen_avg_quality",
        "leverage_index",
        # phase-4
        "wind_out_mph", "temp_f", "is_roof_closed",
        "in_extras", "ghost_runner_on_2nd",
    )]
    nan_counts = out[base_cols].isna().sum()
    if nan_counts.any():
        bad_cols = nan_counts[nan_counts > 0]
        logger.warning("NaN values in features: %s — filling with 0", bad_cols.to_dict())
        out[base_cols] = out[base_cols].fillna(0.0)

    return out


def enrich_with_phase1_features(features: pd.DataFrame) -> pd.DataFrame:
    """
    Append the 8 phase-1 columns to an already-engineered features DataFrame.

    Required (optional) columns on `features` for non-default joins:
        home_pitcher_id, away_pitcher_id   (str)
        park_id                             (str)
        date                                (date or YYYY-MM-DD str)
        pregame_prior_source                (int 0/1/2)

    When source columns are missing, falls back to neutral defaults:
        sp_quality=100, sp_recent_form=0, park_run_factor=1.0, source=1 (elo).

    The audit step (models/audit_features.py, T13) will detect when these
    features carry no signal and REJECT them — which is the correct behavior
    for offline training without pitcher_id snapshots. The same code path is
    used in live inference (sports/mlb/winprob_inference.py, T10) where
    real pitcher IDs are present.
    """
    out = features.copy()

    # ── pitcher quality: try join, else neutral defaults ──────────────────
    pq_path = FEATURE_DIR / "pitcher_quality.parquet"
    if pq_path.exists() and "home_pitcher_id" in out.columns and "date" in out.columns:
        pq = pd.read_parquet(pq_path)
        pq["as_of_date"] = pd.to_datetime(pq["as_of_date"]).dt.date
        pq["pitcher_id"] = pq["pitcher_id"].astype(str)
        out["_join_date"] = pd.to_datetime(out["date"]).dt.date
        # Coerce snapshot IDs to str to match pitcher_quality (which stores str MLBAM)
        out["home_pitcher_id"] = out["home_pitcher_id"].astype(str)
        out["away_pitcher_id"] = out["away_pitcher_id"].astype(str)
        h = pq.rename(columns={"pitcher_id": "home_pitcher_id",
                               "as_of_date": "_join_date",
                               "sp_quality": "home_sp_quality",
                               "sp_recent_form": "home_sp_recent_form"})[
            ["home_pitcher_id", "_join_date", "home_sp_quality", "home_sp_recent_form"]]
        a = pq.rename(columns={"pitcher_id": "away_pitcher_id",
                               "as_of_date": "_join_date",
                               "sp_quality": "away_sp_quality",
                               "sp_recent_form": "away_sp_recent_form"})[
            ["away_pitcher_id", "_join_date", "away_sp_quality", "away_sp_recent_form"]]
        out = out.merge(h, on=["home_pitcher_id", "_join_date"], how="left")
        out = out.merge(a, on=["away_pitcher_id", "_join_date"], how="left")
        out = out.drop(columns=["_join_date"])
    else:
        logger.warning("phase-1 enrichment: pitcher_quality not joined "
                       "(missing parquet or pitcher_id columns); using neutral defaults")

    out["home_sp_quality"] = out.get("home_sp_quality", 100.0)
    out["away_sp_quality"] = out.get("away_sp_quality", 100.0)
    out["home_sp_recent_form"] = out.get("home_sp_recent_form", 0.0)
    out["away_sp_recent_form"] = out.get("away_sp_recent_form", 0.0)
    out["home_sp_quality"] = out["home_sp_quality"].fillna(100.0)
    out["away_sp_quality"] = out["away_sp_quality"].fillna(100.0)
    out["home_sp_recent_form"] = out["home_sp_recent_form"].fillna(0.0)
    out["away_sp_recent_form"] = out["away_sp_recent_form"].fillna(0.0)

    out["sp_quality_diff"] = out["away_sp_quality"] - out["home_sp_quality"]

    # ── park factor: try join, else neutral 1.0 ────────────────────────────
    pf_path = FEATURE_DIR / "park_factors.parquet"
    if pf_path.exists() and "park_id" in out.columns and "season" in out.columns:
        pf = pd.read_parquet(pf_path)
        pf = pf[["park_id", "season", "run_factor"]].rename(columns={"run_factor": "park_run_factor"})
        out = out.merge(pf, on=["park_id", "season"], how="left")
    else:
        logger.warning("phase-1 enrichment: park_factors not joined "
                       "(missing parquet or park_id/season); using neutral 1.0")

    out["park_run_factor"] = out.get("park_run_factor", 1.0)
    out["park_run_factor"] = out["park_run_factor"].fillna(1.0)
    out["park_run_factor_x_late"] = (out["park_run_factor"] - 1.0) * out["late_game"]

    # ── pregame_prior_source: passthrough or default ──────────────────────
    if "pregame_prior_source" not in out.columns:
        logger.warning("phase-1 enrichment: pregame_prior_source missing; defaulting to 1 (elo)")
        out["pregame_prior_source"] = 1
    out["pregame_prior_source"] = out["pregame_prior_source"].astype(float)

    # ── Phase-2: batter quality enrichment ───────────────────────────────────
    bq_path = FEATURE_DIR / "batter_quality.parquet"
    can_join_batter = (
        bq_path.exists()
        and "batter_id" in out.columns
        and "date" in out.columns
        and "home_lineup_ids" in out.columns
        and "away_lineup_ids" in out.columns
        and "current_lineup_position" in out.columns
        and "batter_stand" in out.columns
    )

    if can_join_batter:
        bq = pd.read_parquet(bq_path)
        bq["as_of_date"] = pd.to_datetime(bq["as_of_date"]).dt.date
        bq["batter_id"] = bq["batter_id"].astype(str)
        bq_lookup = dict(zip(zip(bq["batter_id"], bq["as_of_date"]), bq["batter_xwoba"]))

        def _xwoba_for(bid, d):
            return bq_lookup.get((str(bid), d), 100.0)

        join_dates = pd.to_datetime(out["date"]).dt.date
        out["current_batter_xwoba"] = [
            _xwoba_for(b, d) for b, d in zip(out["batter_id"], join_dates)
        ]

        def _next3(row, d):
            half = row["half"]
            pos = int(row["current_lineup_position"])
            lineup = row["away_lineup_ids"] if half == 0 else row["home_lineup_ids"]
            if lineup is None or len(lineup) == 0 or pos < 1:
                return 100.0
            ids = []
            for i in range(1, 4):
                idx = (pos - 1 + i) % len(lineup)
                ids.append(lineup[idx])
            if not ids:
                return 100.0
            return sum(_xwoba_for(b, d) for b in ids) / len(ids)

        def _lineup_avg(row, d):
            half = row["half"]
            lineup = row["away_lineup_ids"] if half == 0 else row["home_lineup_ids"]
            if lineup is None or len(lineup) == 0:
                return 100.0
            return sum(_xwoba_for(b, d) for b in lineup) / len(lineup)

        out["next3_avg_xwoba"] = [
            _next3(row, d) for (_, row), d in zip(out.iterrows(), join_dates)
        ]
        out["lineup_avg_xwoba"] = [
            _lineup_avg(row, d) for (_, row), d in zip(out.iterrows(), join_dates)
        ]
    else:
        logger.warning("phase-2 enrichment: required columns missing; using neutral defaults")
        out["current_batter_xwoba"] = 100.0
        out["next3_avg_xwoba"] = 100.0
        out["lineup_avg_xwoba"] = 100.0

    # Platoon advantage flag (derived from row, no parquet needed)
    if ("batter_stand" in out.columns
            and "home_pitcher_p_throws" in out.columns
            and "away_pitcher_p_throws" in out.columns):
        def _platoon(row):
            stand = row["batter_stand"]
            half = row["half"]
            p_throws = row["home_pitcher_p_throws"] if half == 0 else row["away_pitcher_p_throws"]
            if stand == "S":
                return 1.0
            if (stand == "L" and p_throws == "R") or (stand == "R" and p_throws == "L"):
                return 1.0
            return 0.0
        out["current_batter_platoon_advantage"] = out.apply(_platoon, axis=1).astype(float)
    else:
        out["current_batter_platoon_advantage"] = 0.0

    out["current_batter_xwoba_x_late"] = (out["current_batter_xwoba"] - 100.0) * out["late_game"]

    # ── Phase-3: bullpen + leverage ──────────────────────────────────────────
    rq_path = FEATURE_DIR / "reliever_quality.parquet"
    bpq_path = FEATURE_DIR / "bullpen_quality.parquet"
    li_path = FEATURE_DIR / "leverage_index.parquet"

    # Reliever quality (per-pitcher, point-in-time)
    if rq_path.exists() and "home_pitcher_id" in out.columns and "date" in out.columns:
        rq = pd.read_parquet(rq_path)
        rq["as_of_date"] = pd.to_datetime(rq["as_of_date"]).dt.date
        rq["pitcher_id"] = rq["pitcher_id"].astype(str)
        rq_lookup = dict(zip(zip(rq["pitcher_id"], rq["as_of_date"]), rq["reliever_quality"]))
        join_dates = pd.to_datetime(out["date"]).dt.date
        def _rel(pid, d):
            return rq_lookup.get((str(pid), d), None)
        out["home_reliever_quality"] = [
            (_rel(pid, d) if is_bp else out["home_sp_quality"].iloc[i]) or out["home_sp_quality"].iloc[i]
            for i, (pid, d, is_bp) in enumerate(zip(out["home_pitcher_id"], join_dates, out["home_is_bullpen"]))
        ]
        out["away_reliever_quality"] = [
            (_rel(pid, d) if is_bp else out["away_sp_quality"].iloc[i]) or out["away_sp_quality"].iloc[i]
            for i, (pid, d, is_bp) in enumerate(zip(out["away_pitcher_id"], join_dates, out["away_is_bullpen"]))
        ]
    else:
        out["home_reliever_quality"] = out.get("home_sp_quality", 100.0)
        out["away_reliever_quality"] = out.get("away_sp_quality", 100.0)

    # Bullpen avg quality
    if bpq_path.exists() and "home_team" in out.columns and "date" in out.columns:
        bpq = pd.read_parquet(bpq_path)
        bpq["as_of_date"] = pd.to_datetime(bpq["as_of_date"]).dt.date
        bpq_lookup = dict(zip(zip(bpq["team"], bpq["as_of_date"]), bpq["bullpen_avg_quality"]))
        join_dates = pd.to_datetime(out["date"]).dt.date
        def _bp(team, d):
            exact = bpq_lookup.get((team, d))
            return exact if exact is not None else 100.0
        out["home_bullpen_avg_quality"] = [_bp(t, d) for t, d in zip(out["home_team"], join_dates)]
        out["away_bullpen_avg_quality"] = [_bp(t, d) for t, d in zip(out["away_team"], join_dates)]
    else:
        out["home_bullpen_avg_quality"] = 100.0
        out["away_bullpen_avg_quality"] = 100.0

    # Leverage index
    if li_path.exists() and all(c in out.columns for c in ["inning", "outs", "base_state", "score_diff"]):
        li = pd.read_parquet(li_path)
        li_lookup = {
            (int(r["inning"]), int(r["outs"]), int(r["base_state"]), int(r["score_bucket"])):
                float(r["leverage_index"])
            for _, r in li.iterrows()
        }
        def _li(inn, o, bs, sd):
            bucket = max(-5, min(5, int(sd)))
            key = (int(inn), int(o), int(bs), bucket)
            if key in li_lookup:
                return li_lookup[key]
            if inn > 9:
                fb = (9, int(o), int(bs), bucket)
                if fb in li_lookup:
                    return li_lookup[fb]
            return 1.0
        out["leverage_index"] = [
            _li(inn, o, bs, sd) for inn, o, bs, sd in zip(
                out["inning"], out["outs"], out["base_state"], out["score_diff"]
            )
        ]
    else:
        out["leverage_index"] = 1.0

    # ── Phase-4: weather + extras ────────────────────────────────────────────
    gw_path = FEATURE_DIR / "game_weather.parquet"
    if gw_path.exists() and "game_id" in out.columns:
        gw = pd.read_parquet(gw_path)
        gw_lookup = {str(r["game_id"]): (float(r["temp_f"]), float(r["wind_out_mph"]),
                                         int(r["is_roof_closed"]))
                     for _, r in gw.iterrows()}
        def _get(g):
            v = gw_lookup.get(str(g))
            return v if v is not None else (70.0, 0.0, 1)
        weather_vals = [_get(g) for g in out["game_id"]]
        out["temp_f"] = [v[0] for v in weather_vals]
        out["wind_out_mph"] = [v[1] for v in weather_vals]
        out["is_roof_closed"] = [float(v[2]) for v in weather_vals]
    else:
        out["temp_f"] = 70.0
        out["wind_out_mph"] = 0.0
        out["is_roof_closed"] = 1.0

    # Extras features (pure derived — no parquet needed)
    if "in_extras" in out.columns:
        out["in_extras"] = out["in_extras"].astype(float)
    else:
        out["in_extras"] = (out["inning"] > 9).astype(float)
    if "ghost_runner_on_2nd" in out.columns:
        out["ghost_runner_on_2nd"] = out["ghost_runner_on_2nd"].astype(float)
    else:
        out["ghost_runner_on_2nd"] = (
            (out["inning"] > 9) & (out["season"] >= 2020) & (out["outs"] == 0)
        ).astype(float)

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
    logger.info("Engineered features: %d rows, %d base columns", len(features), len(FEATURE_COLUMNS) - 8)

    # Phase-1 enrichment
    features = enrich_with_phase1_features(features)
    logger.info("Phase-1 enrichment applied; total feature columns: %d", len(FEATURE_COLUMNS))

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
