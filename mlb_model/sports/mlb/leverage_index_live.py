"""sports/mlb/leverage_index_live.py — Live LI lookup by game state."""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)
_TABLE: Optional[pd.DataFrame] = None
_TABLE_PATH = Path("data/features/leverage_index.parquet")
_LOOKUP: Optional[dict] = None


def _load_table() -> pd.DataFrame:
    global _TABLE, _LOOKUP
    if _TABLE is None:
        if _TABLE_PATH.exists():
            _TABLE = pd.read_parquet(_TABLE_PATH)
        else:
            _TABLE = pd.DataFrame(columns=["inning", "outs", "base_state",
                                           "score_bucket", "leverage_index"])
        _LOOKUP = None
    return _TABLE


def _set_test_table(df: Optional[pd.DataFrame]) -> None:
    global _TABLE, _LOOKUP
    _TABLE = df
    _LOOKUP = None


def _build_lookup() -> dict:
    global _LOOKUP
    if _LOOKUP is None:
        tbl = _load_table()
        _LOOKUP = {
            (int(r["inning"]), int(r["outs"]), int(r["base_state"]), int(r["score_bucket"])):
                float(r["leverage_index"])
            for _, r in tbl.iterrows()
        }
    return _LOOKUP


def lookup_leverage_index(inning: int, outs: int, base_state: int, score_diff: int) -> float:
    """Return leverage index for this state. 1.0 (neutral) if unknown."""
    score_bucket = max(-5, min(5, int(score_diff)))
    lookup = _build_lookup()
    key = (int(inning), int(outs), int(base_state), score_bucket)
    if key in lookup:
        return lookup[key]
    if inning > 9:
        fallback = (9, int(outs), int(base_state), score_bucket)
        if fallback in lookup:
            return lookup[fallback]
    return 1.0
