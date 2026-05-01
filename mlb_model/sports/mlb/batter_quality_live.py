"""
sports/mlb/batter_quality_live.py — Live (batter_id, date) → batter_xwoba.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional, Iterable
import pandas as pd

logger = logging.getLogger(__name__)
_TABLE: Optional[pd.DataFrame] = None
_TABLE_PATH = Path("data/features/batter_quality.parquet")
LEAGUE_MEAN = 100.0


@dataclass
class BatterQuality:
    batter_xwoba: float
    n_pa_std: int
    imputed: bool


def _load_table() -> pd.DataFrame:
    global _TABLE
    if _TABLE is None:
        if _TABLE_PATH.exists():
            _TABLE = pd.read_parquet(_TABLE_PATH)
            _TABLE["as_of_date"] = pd.to_datetime(_TABLE["as_of_date"]).dt.date
        else:
            _TABLE = pd.DataFrame(columns=["batter_id", "as_of_date",
                                           "batter_xwoba", "n_pa_std"])
    return _TABLE


def _set_test_table(df: Optional[pd.DataFrame]) -> None:
    global _TABLE
    _TABLE = df


def lookup_batter_xwoba(batter_id: str, as_of: date) -> BatterQuality:
    table = _load_table()
    if table.empty:
        return BatterQuality(LEAGUE_MEAN, 0, imputed=True)
    rows = table[table["batter_id"] == str(batter_id)]
    if rows.empty:
        return BatterQuality(LEAGUE_MEAN, 0, imputed=True)
    exact = rows[rows["as_of_date"] == as_of]
    if not exact.empty:
        r = exact.iloc[0]
    else:
        prior = rows[rows["as_of_date"] <= as_of].sort_values("as_of_date", ascending=False)
        if prior.empty:
            return BatterQuality(LEAGUE_MEAN, 0, imputed=True)
        r = prior.iloc[0]
    return BatterQuality(
        batter_xwoba=float(r["batter_xwoba"]),
        n_pa_std=int(r["n_pa_std"]),
        imputed=False,
    )


def lookup_batters_avg_xwoba(batter_ids: Iterable, as_of: date) -> float:
    """Mean batter_xwoba across the given batter_ids; impute 100 for unknowns."""
    ids = [str(b) for b in batter_ids]
    if not ids:
        return LEAGUE_MEAN
    vals = [lookup_batter_xwoba(b, as_of).batter_xwoba for b in ids]
    return sum(vals) / len(vals)
