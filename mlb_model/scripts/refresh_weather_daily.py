"""
scripts/refresh_weather_daily.py — Daily weather refresh.

Fetches forecast weather for today's MLB games and appends to game_weather.parquet.
Also backfills yesterday's games (in case they weren't fetched).
"""
from __future__ import annotations
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logger = logging.getLogger(__name__)

WEATHER_PATH = Path("data/features/game_weather.parquet")


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    from data.foundation.weather_backfill import backfill

    current_year = date.today().year
    df = backfill(seasons=[current_year])
    if df.empty:
        print("No games found to fetch weather for.")
        return 0

    existing = pd.read_parquet(WEATHER_PATH) if WEATHER_PATH.exists() else pd.DataFrame()
    if existing.empty:
        out = df
    else:
        combined = pd.concat([existing, df], ignore_index=True)
        out = combined.drop_duplicates(subset=["game_id"], keep="last")

    WEATHER_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = WEATHER_PATH.with_suffix(".parquet.tmp")
    out.to_parquet(tmp, index=False)
    os.replace(tmp, WEATHER_PATH)
    print(f"Refreshed game_weather.parquet: total rows = {len(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
