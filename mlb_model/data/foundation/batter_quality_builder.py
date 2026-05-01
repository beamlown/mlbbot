"""
data/foundation/batter_quality_builder.py

Point-in-time batter quality table.

For each (batter_id, as_of_date) compute:
    batter_xwoba: hybrid xwOBA scaled to 100-center (higher = better hitter).
                  Hybrid: 0.6 * current_STD + 0.4 * prior_season,
                  regressed to league mean by PA.

CRITICAL: only PAs with game_date < as_of_date may contribute.
"""
from __future__ import annotations
import logging
from datetime import date
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("data/features/batter_quality.parquet")
LEAGUE_AVG_XWOBA = 0.320
REGRESSION_PA = 200
PRIOR_WEIGHT = 0.4


def _hybrid_xwoba(prior_xwoba: float | None, std_xwoba: float | None,
                  std_pa: float, league_xwoba: float = LEAGUE_AVG_XWOBA,
                  regression_pa: float = REGRESSION_PA) -> float:
    """Returns batter_xwoba on 100-center scale."""
    has_prior = prior_xwoba is not None and not pd.isna(prior_xwoba)
    has_std = std_xwoba is not None and not pd.isna(std_xwoba)
    if not has_prior and not has_std:
        return 100.0
    if not has_prior:
        raw = std_xwoba
    elif not has_std:
        raw = prior_xwoba
    else:
        raw = (1.0 - PRIOR_WEIGHT) * std_xwoba + PRIOR_WEIGHT * prior_xwoba
    # Regress to league mean by sample
    weight = std_pa / (std_pa + regression_pa) if std_pa > 0 else 0.0
    regressed = weight * raw + (1.0 - weight) * league_xwoba
    return (regressed / league_xwoba) * 100.0


def compute_batter_quality_pointtime(
    history: pd.DataFrame,
    snapshot_dates: list[date] | None = None,
) -> pd.DataFrame:
    """
    history columns: batter_id, game_date, xwoba_mean, pa, xwoba_pa, season

    snapshot_dates: dates to compute "as of"; defaults to all unique game_dates
    plus a couple of test fixture dates.
    """
    cols = ["batter_id", "as_of_date", "batter_xwoba", "n_pa_std"]
    if history.empty:
        return pd.DataFrame(columns=cols)

    h = history.copy()
    h["game_date"] = pd.to_datetime(h["game_date"]).dt.date
    h["pa"] = h["pa"].astype(int)
    h["xwoba_weight"] = h["xwoba_pa"].fillna(0).astype(int)
    h["xwoba_total"] = h["xwoba_mean"].fillna(0) * h["xwoba_weight"]

    if snapshot_dates is None:
        snapshot_dates = sorted(set(h["game_date"].tolist()) |
                                {date(2024, 3, 1), date(2025, 5, 1)})

    batters = h["batter_id"].unique()
    out_rows = []
    for batter_id in batters:
        bh = h[h["batter_id"] == batter_id]
        for as_of in snapshot_dates:
            past = bh[bh["game_date"] < as_of]
            if past.empty:
                continue
            cur_season = as_of.year
            std = past[past["season"] == cur_season]
            prior = past[past["season"] == cur_season - 1]

            std_pa = float(std["pa"].sum()) if not std.empty else 0.0
            std_xpa = float(std["xwoba_weight"].sum()) if not std.empty else 0.0
            std_xwoba = (float(std["xwoba_total"].sum()) / std_xpa) if std_xpa > 0 else None
            prior_xpa = float(prior["xwoba_weight"].sum()) if not prior.empty else 0.0
            prior_xwoba = (float(prior["xwoba_total"].sum()) / prior_xpa) if prior_xpa > 0 else None

            batter_xwoba = _hybrid_xwoba(prior_xwoba, std_xwoba, std_pa)
            out_rows.append({
                "batter_id": batter_id,
                "as_of_date": as_of,
                "batter_xwoba": batter_xwoba,
                "n_pa_std": int(std_pa),
            })

    return pd.DataFrame(out_rows, columns=cols)


def build_from_statcast(seasons: list[int] | None = None) -> pd.DataFrame:
    """End-to-end: aggregate statcast → point-in-time table."""
    from data.foundation.statcast_batter_aggregator import aggregate_from_statcast_dir
    history = aggregate_from_statcast_dir(seasons=seasons)
    history["batter_id"] = history["batter_id"].astype(str)
    return compute_batter_quality_pointtime(history)


def main() -> None:
    seasons = list(range(2018, 2026))
    df = build_from_statcast(seasons)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
