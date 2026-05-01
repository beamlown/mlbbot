"""sports/mlb/reliever_quality_live.py — Live (pitcher_id, date) → reliever_quality."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)
_TABLE: Optional[pd.DataFrame] = None
_TABLE_PATH = Path("data/features/reliever_quality.parquet")
LEAGUE_MEAN = 100.0


@dataclass
class RelieverQuality:
    reliever_quality: float
    n_outings_std: int
    imputed: bool


def _load_table() -> pd.DataFrame:
    global _TABLE
    if _TABLE is None:
        if _TABLE_PATH.exists():
            _TABLE = pd.read_parquet(_TABLE_PATH)
            _TABLE["as_of_date"] = pd.to_datetime(_TABLE["as_of_date"]).dt.date
        else:
            _TABLE = pd.DataFrame(columns=["pitcher_id", "as_of_date",
                                           "reliever_quality", "n_outings_std"])
    return _TABLE


def _set_test_table(df: Optional[pd.DataFrame]) -> None:
    global _TABLE
    _TABLE = df


def lookup_reliever_quality(pitcher_id: str, as_of: date) -> RelieverQuality:
    table = _load_table()
    if table.empty:
        return RelieverQuality(LEAGUE_MEAN, 0, imputed=True)
    rows = table[table["pitcher_id"] == str(pitcher_id)]
    if rows.empty:
        return RelieverQuality(LEAGUE_MEAN, 0, imputed=True)
    exact = rows[rows["as_of_date"] == as_of]
    if not exact.empty:
        r = exact.iloc[0]
    else:
        prior = rows[rows["as_of_date"] <= as_of].sort_values("as_of_date", ascending=False)
        if prior.empty:
            return RelieverQuality(LEAGUE_MEAN, 0, imputed=True)
        r = prior.iloc[0]
    return RelieverQuality(
        reliever_quality=float(r["reliever_quality"]),
        n_outings_std=int(r["n_outings_std"]),
        imputed=False,
    )
