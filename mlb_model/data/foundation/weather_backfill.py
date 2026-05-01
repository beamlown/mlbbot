"""
data/foundation/weather_backfill.py

Batch fetch weather for every unique (game_pk, park_id, date) in snapshots.
Writes to data/features/game_weather.parquet.

Indoor/closed-roof games get neutral defaults (no API call).

Usage:
    python -m data.foundation.weather_backfill [--seasons 2018 2019 ...]
"""
from __future__ import annotations
import argparse
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

from data.foundation.weather_fetcher import (
    fetch_weather_at, project_wind, WeatherError, WeatherSnapshot,
)
from data.foundation.park_metadata_builder import build_park_metadata

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("data/features/game_weather.parquet")
SNAPSHOT_DIR = Path("data/features")
REQUEST_SLEEP_SEC = 0.3


def _collect_game_dates(seasons: list[int] | None = None) -> pd.DataFrame:
    """Pull unique (game_id, park_id, date) rows from snapshot parquets."""
    parquets = sorted(SNAPSHOT_DIR.glob("snapshots_*.parquet"))
    frames = []
    for p in parquets:
        if seasons is not None:
            year = int(p.stem.split("_")[-1])
            if year not in seasons:
                continue
        df = pd.read_parquet(p, columns=["game_id", "park_id", "date"])
        frames.append(df.drop_duplicates(subset=["game_id"]))
    if not frames:
        return pd.DataFrame(columns=["game_id", "park_id", "date"])
    games = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["game_id"])
    return games


def backfill(seasons: list[int] | None = None) -> pd.DataFrame:
    parks = build_park_metadata().set_index("park_id")
    games = _collect_game_dates(seasons)
    logger.info("Backfilling weather for %d unique games", len(games))

    rows = []
    for i, g in games.iterrows():
        park_id = str(g["park_id"])
        if park_id not in parks.index:
            rows.append({
                "game_id": str(g["game_id"]), "park_id": park_id,
                "temp_f": 70.0, "wind_mph": 0.0, "wind_from_deg": 0.0,
                "wind_out_mph": 0.0, "is_roof_closed": 1,
            })
            continue
        meta = parks.loc[park_id]
        if int(meta["is_indoor"]) == 1:
            rows.append({
                "game_id": str(g["game_id"]), "park_id": park_id,
                "temp_f": 70.0, "wind_mph": 0.0, "wind_from_deg": 0.0,
                "wind_out_mph": 0.0, "is_roof_closed": 1,
            })
            continue

        try:
            date_obj = pd.to_datetime(str(g["date"])).to_pydatetime().replace(
                hour=19, minute=0, tzinfo=timezone.utc)
        except Exception:
            continue
        try:
            snap = fetch_weather_at(float(meta["latitude"]), float(meta["longitude"]),
                                    date_obj, use_archive=True)
        except WeatherError as e:
            logger.warning("weather fetch failed for %s on %s: %s",
                           park_id, g["date"], e)
            continue

        wind_out = project_wind(snap.wind_mph, snap.wind_from_deg,
                                float(meta["outfield_orientation_deg"]))
        rows.append({
            "game_id": str(g["game_id"]), "park_id": park_id,
            "temp_f": snap.temp_f, "wind_mph": snap.wind_mph,
            "wind_from_deg": snap.wind_from_deg,
            "wind_out_mph": wind_out, "is_roof_closed": 0,
        })
        time.sleep(REQUEST_SLEEP_SEC)
        if (i + 1) % 200 == 0:
            logger.info("  ...%d/%d games fetched", i + 1, len(games))

    return pd.DataFrame(rows)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Backfill historical weather per game_pk")
    parser.add_argument("--seasons", nargs="+", type=int, default=None)
    args = parser.parse_args()

    df = backfill(args.seasons)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
