"""sports/mlb/bullpen_quality_live.py - Live (team, date) -> bullpen_avg_quality."""
from __future__ import annotations
import logging
from datetime import date
from pathlib import Path
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)
_TABLE: Optional[pd.DataFrame] = None
_TABLE_PATH = Path("data/features/bullpen_quality.parquet")
LEAGUE_MEAN = 100.0


def _load_table() -> pd.DataFrame:
    global _TABLE
    if _TABLE is None:
        if _TABLE_PATH.exists():
            _TABLE = pd.read_parquet(_TABLE_PATH)
            _TABLE["as_of_date"] = pd.to_datetime(_TABLE["as_of_date"]).dt.date
        else:
            _TABLE = pd.DataFrame(columns=["team", "as_of_date",
                                           "bullpen_avg_quality", "n_relievers"])
    return _TABLE


def _set_test_table(df: Optional[pd.DataFrame]) -> None:
    global _TABLE
    _TABLE = df


def lookup_bullpen_quality(team: str, as_of: date) -> float:
    table = _load_table()
    if table.empty:
        return LEAGUE_MEAN
    rows = table[table["team"] == team]
    if rows.empty:
        return LEAGUE_MEAN
    exact = rows[rows["as_of_date"] == as_of]
    if not exact.empty:
        return float(exact.iloc[0]["bullpen_avg_quality"])
    prior = rows[rows["as_of_date"] <= as_of].sort_values("as_of_date", ascending=False)
    if prior.empty:
        return LEAGUE_MEAN
    return float(prior.iloc[0]["bullpen_avg_quality"])
