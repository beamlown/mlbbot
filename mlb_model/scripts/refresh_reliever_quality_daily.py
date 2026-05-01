"""scripts/refresh_reliever_quality_daily.py — Daily incremental refresh of reliever_quality.parquet."""
from __future__ import annotations
import logging
import os
from datetime import date, timedelta
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

RELIEVER_PATH = Path("data/features/reliever_quality.parquet")
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
    if "pitcher" not in schema_cols:
        return pd.DataFrame()
    df = pd.read_parquet(target_file, columns=["pitcher", "game_pk", "game_date", "events"])
    if df.empty:
        return pd.DataFrame()
    df["game_date"] = pd.to_datetime(df["game_date"]).dt.date
    return df[df["game_date"] == target_date]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    yesterday = date.today() - timedelta(days=1)
    pitches = _load_yesterdays_pitches(yesterday)
    if pitches.empty:
        print(f"No Statcast for {yesterday}; nothing to refresh.")
        return 0

    from data.foundation.statcast_reliever_aggregator import aggregate_reliever_per_game
    from data.foundation.reliever_quality_builder import compute_reliever_quality_pointtime

    new_history = aggregate_reliever_per_game(pitches)
    if new_history.empty:
        print(f"No relief outings on {yesterday}.")
        return 0
    new_history["pitcher_id"] = new_history["pitcher_id"].astype(str)

    existing = pd.read_parquet(RELIEVER_PATH) if RELIEVER_PATH.exists() else pd.DataFrame()

    yesterday_rq = compute_reliever_quality_pointtime(
        new_history[["pitcher_id", "game_date", "ip", "fip", "season"]],
        snapshot_dates=[yesterday + timedelta(days=1)],
    )
    if existing.empty:
        out = yesterday_rq
    else:
        out = pd.concat([existing, yesterday_rq], ignore_index=True)
        out = out.drop_duplicates(subset=["pitcher_id", "as_of_date"], keep="last")

    RELIEVER_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = RELIEVER_PATH.with_suffix(".parquet.tmp")
    out.to_parquet(tmp, index=False)
    os.replace(tmp, RELIEVER_PATH)
    print(f"Refreshed reliever_quality.parquet: +{len(yesterday_rq)} rows for {yesterday}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
