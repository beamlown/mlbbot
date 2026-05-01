"""
sports/mlb/pitcher_quality_live.py

Live (pitcher_id, as_of_date) → quality stats lookup.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)
_TABLE: Optional[pd.DataFrame] = None
_TABLE_PATH = Path("data/features/pitcher_quality.parquet")
LEAGUE_MEAN_QUALITY = 100.0


@dataclass
class PitcherQuality:
    sp_quality: float           # FIP- scale (100 avg, lower better)
    sp_recent_form: float       # baseline - recent_30d (positive = improving)
    n_starts_std: int
    imputed: bool               # True if league-mean substituted


def _load_table() -> pd.DataFrame:
    global _TABLE
    if _TABLE is None:
        if not _TABLE_PATH.exists():
            logger.warning("pitcher_quality.parquet not found at %s; using empty", _TABLE_PATH)
            _TABLE = pd.DataFrame(columns=["pitcher_id", "as_of_date",
                                           "sp_quality", "sp_recent_form", "n_starts_std"])
        else:
            _TABLE = pd.read_parquet(_TABLE_PATH)
            _TABLE["as_of_date"] = pd.to_datetime(_TABLE["as_of_date"]).dt.date
    return _TABLE


def _set_test_table(df: Optional[pd.DataFrame]) -> None:
    global _TABLE
    _TABLE = df


def lookup_pitcher_quality(pitcher_id: str, as_of: date) -> PitcherQuality:
    table = _load_table()
    if table.empty:
        return PitcherQuality(LEAGUE_MEAN_QUALITY, 0.0, 0, imputed=True)

    rows = table[table["pitcher_id"] == pitcher_id]
    if rows.empty:
        logger.info("No quality row for pitcher_id=%s, imputing league mean", pitcher_id)
        return PitcherQuality(LEAGUE_MEAN_QUALITY, 0.0, 0, imputed=True)

    exact = rows[rows["as_of_date"] == as_of]
    if not exact.empty:
        r = exact.iloc[0]
    else:
        prior = rows[rows["as_of_date"] <= as_of].sort_values("as_of_date", ascending=False)
        if prior.empty:
            return PitcherQuality(LEAGUE_MEAN_QUALITY, 0.0, 0, imputed=True)
        r = prior.iloc[0]

    return PitcherQuality(
        sp_quality=float(r["sp_quality"]),
        sp_recent_form=float(r["sp_recent_form"]),
        n_starts_std=int(r["n_starts_std"]),
        imputed=False,
    )
