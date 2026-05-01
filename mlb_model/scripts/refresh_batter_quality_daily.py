"""
scripts/refresh_batter_quality_daily.py — Incremental daily refresh of batter_quality.parquet.
Mirrors scripts/refresh_pitcher_quality_daily.py but for batters.
"""
from __future__ import annotations
import logging
import os
from datetime import date, timedelta
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

BATTER_QUALITY_PATH = Path("data/features/batter_quality.parquet")
STATCAST_DIR = Path("data/raw/statcast")


def _load_yesterdays_pitches(target_date: date) -> pd.DataFrame:
    import pyarrow.parquet as pq
    target_file = STATCAST_DIR / f"{target_date.year}_{target_date.month:02d}.parquet"
    if not target_file.exists():
        return pd.DataFrame()
    try:
        schema_cols = pq.read_schema(target_file).names
    except Exception:
        return pd.DataFrame()
    if "batter" not in schema_cols:
        return pd.DataFrame()
    df = pd.read_parquet(target_file, columns=["batter", "game_date", "events",
                                               "estimated_woba_using_speedangle"])
    if df.empty:
        return pd.DataFrame()
    df["game_date"] = pd.to_datetime(df["game_date"]).dt.date
    return df[df["game_date"] == target_date]


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    yesterday = date.today() - timedelta(days=1)

    pitches = _load_yesterdays_pitches(yesterday)
    if pitches.empty:
        print(f"No Statcast pitches for {yesterday}; nothing to refresh.")
        return 0

    from data.foundation.statcast_batter_aggregator import aggregate_per_batter_per_date
    from data.foundation.batter_quality_builder import compute_batter_quality_pointtime

    new_history = aggregate_per_batter_per_date(pitches)
    if new_history.empty:
        print(f"No qualifying PAs on {yesterday}.")
        return 0
    new_history["batter_id"] = new_history["batter_id"].astype(str)

    if BATTER_QUALITY_PATH.exists():
        existing = pd.read_parquet(BATTER_QUALITY_PATH)
    else:
        existing = pd.DataFrame()

    yesterday_bq = compute_batter_quality_pointtime(
        new_history, snapshot_dates=[yesterday + timedelta(days=1)],
    )
    if existing.empty:
        out = yesterday_bq
    else:
        out = pd.concat([existing, yesterday_bq], ignore_index=True)
        out = out.drop_duplicates(subset=["batter_id", "as_of_date"], keep="last")

    BATTER_QUALITY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = BATTER_QUALITY_PATH.with_suffix(".parquet.tmp")
    out.to_parquet(tmp, index=False)
    os.replace(tmp, BATTER_QUALITY_PATH)
    print(f"Refreshed batter_quality.parquet: +{len(yesterday_bq)} rows for {yesterday}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
