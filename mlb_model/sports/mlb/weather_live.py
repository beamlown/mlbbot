"""sports/mlb/weather_live.py -- Live (game_id) -> weather row lookup."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)
_TABLE: Optional[pd.DataFrame] = None
_TABLE_PATH = Path("data/features/game_weather.parquet")


@dataclass
class WeatherRow:
    temp_f: float
    wind_out_mph: float
    is_roof_closed: bool


def _load_table() -> pd.DataFrame:
    global _TABLE
    if _TABLE is None:
        if _TABLE_PATH.exists():
            _TABLE = pd.read_parquet(_TABLE_PATH)
        else:
            _TABLE = pd.DataFrame(columns=[
                "game_id", "park_id", "temp_f", "wind_mph", "wind_from_deg",
                "wind_out_mph", "is_roof_closed",
            ])
    return _TABLE


def _set_test_table(df: Optional[pd.DataFrame]) -> None:
    global _TABLE
    _TABLE = df


def lookup_weather_for_game(game_id: str) -> WeatherRow:
    """Return weather for a given game_id. Neutral defaults if missing."""
    table = _load_table()
    if table.empty:
        return WeatherRow(temp_f=70.0, wind_out_mph=0.0, is_roof_closed=True)
    rows = table[table["game_id"] == str(game_id)]
    if rows.empty:
        return WeatherRow(temp_f=70.0, wind_out_mph=0.0, is_roof_closed=True)
    r = rows.iloc[0]
    return WeatherRow(
        temp_f=float(r["temp_f"]),
        wind_out_mph=float(r["wind_out_mph"]),
        is_roof_closed=bool(int(r["is_roof_closed"])),
    )
