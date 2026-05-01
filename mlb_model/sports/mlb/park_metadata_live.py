"""sports/mlb/park_metadata_live.py — Live (park_id) -> park metadata lookup."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)
_TABLE: Optional[pd.DataFrame] = None
_TABLE_PATH = Path("data/features/park_metadata.parquet")


@dataclass
class ParkMetadata:
    park_id: str
    park_name: str
    latitude: float
    longitude: float
    outfield_orientation_deg: float
    has_roof: bool
    is_retractable: bool
    is_indoor: bool


def _load_table() -> pd.DataFrame:
    global _TABLE
    if _TABLE is None:
        if _TABLE_PATH.exists():
            _TABLE = pd.read_parquet(_TABLE_PATH)
        else:
            _TABLE = pd.DataFrame(columns=[
                "park_id", "park_name", "latitude", "longitude",
                "outfield_orientation_deg", "has_roof", "is_retractable", "is_indoor",
            ])
    return _TABLE


def _set_test_table(df: Optional[pd.DataFrame]) -> None:
    global _TABLE
    _TABLE = df


def lookup_park_metadata(park_id: str) -> ParkMetadata:
    table = _load_table()
    rows = table[table["park_id"] == park_id]
    if rows.empty:
        logger.info("Unknown park_id=%s, defaulting to indoor neutral", park_id)
        return ParkMetadata(
            park_id=park_id, park_name="unknown",
            latitude=0.0, longitude=0.0, outfield_orientation_deg=0.0,
            has_roof=True, is_retractable=False, is_indoor=True,
        )
    r = rows.iloc[0]
    return ParkMetadata(
        park_id=str(r["park_id"]),
        park_name=str(r["park_name"]),
        latitude=float(r["latitude"]),
        longitude=float(r["longitude"]),
        outfield_orientation_deg=float(r["outfield_orientation_deg"]),
        has_roof=bool(r["has_roof"]),
        is_retractable=bool(r["is_retractable"]),
        is_indoor=bool(r["is_indoor"]),
    )
