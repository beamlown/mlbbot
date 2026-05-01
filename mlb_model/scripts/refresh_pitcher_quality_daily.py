"""
scripts/refresh_pitcher_quality_daily.py

Daily incremental refresh of pitcher_quality.parquet.

Strategy:
  1. Aggregate yesterday's Statcast pitches into per-(pitcher_id, game_pk) FIP rows
  2. Compute point-in-time quality "as of tomorrow" using just yesterday's starts
  3. Append those rows to the existing pitcher_quality history (dedupe on key)
  4. Write back atomically (.tmp -> rename)

Idempotent: re-running on the same day overwrites with identical data.

If yesterday had no Statcast data (off-day, scrape lag), exits 0 with a no-op log.
"""
from __future__ import annotations
import logging
import os
from datetime import date, timedelta
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

PITCHER_QUALITY_PATH = Path("data/features/pitcher_quality.parquet")
STATCAST_DIR = Path("data/raw/statcast")


def _load_yesterdays_pitches(target_date: date) -> pd.DataFrame:
    """Load only the parquet that contains target_date (e.g. 2026_04.parquet).

    Returns empty DataFrame if file missing or empty (e.g. early-month, off-day).
    """
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
    cols = ["pitcher", "game_pk", "game_date", "events"]
    df = pd.read_parquet(target_file, columns=cols)
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

    from data.foundation.statcast_pitcher_aggregator import aggregate_per_pitcher_per_game
    from data.foundation.pitcher_quality_builder import compute_pitcher_quality_pointtime

    new_starts = aggregate_per_pitcher_per_game(pitches)
    new_starts = new_starts[new_starts["fip"].notna() & (new_starts["ip"] >= 4.0)].copy()
    if new_starts.empty:
        print(f"No qualifying starts on {yesterday}.")
        return 0
    new_starts["pitcher_id"] = new_starts["pitcher_id"].astype(str)

    if PITCHER_QUALITY_PATH.exists():
        existing = pd.read_parquet(PITCHER_QUALITY_PATH)
    else:
        existing = pd.DataFrame()

    yesterday_pq = compute_pitcher_quality_pointtime(
        new_starts[["pitcher_id", "game_date", "ip", "fip", "season"]],
        snapshot_dates=[yesterday + timedelta(days=1)],
    )
    if existing.empty:
        out = yesterday_pq
    else:
        out = pd.concat([existing, yesterday_pq], ignore_index=True)
        out = out.drop_duplicates(subset=["pitcher_id", "as_of_date"], keep="last")

    PITCHER_QUALITY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PITCHER_QUALITY_PATH.with_suffix(".parquet.tmp")
    out.to_parquet(tmp, index=False)
    os.replace(tmp, PITCHER_QUALITY_PATH)
    print(f"Refreshed pitcher_quality.parquet: +{len(yesterday_pq)} rows for {yesterday}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
