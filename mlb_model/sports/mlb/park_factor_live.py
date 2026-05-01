"""
sports/mlb/park_factor_live.py

Live lookup of park run factor for the inference path.
Loads data/features/park_factors.parquet at first call, caches in memory.

API:
    lookup_park_factor(park_id, season) -> float    1.0 if unknown
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)
_TABLE: Optional[pd.DataFrame] = None
_TABLE_PATH = Path("data/features/park_factors.parquet")


def _load_table() -> pd.DataFrame:
    global _TABLE
    if _TABLE is None:
        if not _TABLE_PATH.exists():
            logger.warning("park_factors.parquet not found at %s; using empty table", _TABLE_PATH)
            _TABLE = pd.DataFrame(columns=["season", "park_id", "run_factor", "n_games"])
        else:
            _TABLE = pd.read_parquet(_TABLE_PATH)
    return _TABLE


def _set_test_table(df: Optional[pd.DataFrame]) -> None:
    """Test seam — overrides the cached table; pass None to clear."""
    global _TABLE
    _TABLE = df


def lookup_park_factor(park_id: str, season: int) -> float:
    """
    Return the run factor for (park_id, season). 1.0 if unknown.
    Falls back to the most recent season available for that park.
    """
    table = _load_table()
    if table.empty:
        return 1.0
    park_rows = table[table["park_id"] == park_id]
    if park_rows.empty:
        logger.warning("Unknown park_id=%s, returning neutral 1.0", park_id)
        return 1.0
    exact = park_rows[park_rows["season"] == season]
    if not exact.empty:
        return float(exact.iloc[0]["run_factor"])
    prior = park_rows[park_rows["season"] <= season].sort_values("season", ascending=False)
    if not prior.empty:
        return float(prior.iloc[0]["run_factor"])
    return float(park_rows.sort_values("season").iloc[0]["run_factor"])
