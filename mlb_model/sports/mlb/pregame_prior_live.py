"""
sports/mlb/pregame_prior_live.py

Sharp odds (Pinnacle) -> daily Elo -> HFA-only fallback. Never returns the
hardcoded 0.54 default.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)

_SHARP_PATH = Path("data/features/sharp_odds_history.parquet")
_ELO_PATH = Path("data/features/elo_table.parquet")
_SHARP: Optional[pd.DataFrame] = None
_ELO: Optional[dict[str, float]] = None

DEFAULT_RATING = 1500.0
HFA = 24.0


@dataclass
class PriorResult:
    home_prob: float
    source: int     # 0=sharp, 1=elo, 2=default

    @property
    def source_name(self) -> str:
        return ["sharp", "elo", "default"][self.source]


def _load_sharp() -> pd.DataFrame:
    global _SHARP
    if _SHARP is None:
        if _SHARP_PATH.exists():
            _SHARP = pd.read_parquet(_SHARP_PATH)
        else:
            _SHARP = pd.DataFrame(columns=["home_team", "away_team",
                                           "commence_time", "home_prob"])
    return _SHARP


def _load_elo() -> dict[str, float]:
    global _ELO
    if _ELO is None:
        if _ELO_PATH.exists():
            df = pd.read_parquet(_ELO_PATH)
            if "team" in df.columns and "rating" in df.columns:
                latest = df.sort_values("date").drop_duplicates("team", keep="last")
                _ELO = dict(zip(latest["team"], latest["rating"]))
            else:
                _ELO = {}
        else:
            _ELO = {}
    return _ELO


def _set_test_sharp(df: Optional[pd.DataFrame]) -> None:
    global _SHARP
    _SHARP = df


def _set_test_elo(elo: Optional[dict]) -> None:
    global _ELO
    _ELO = elo


def _try_sharp(home: str, away: str, game_date: date) -> Optional[float]:
    sharp = _load_sharp()
    if sharp.empty:
        return None
    sharp = sharp.copy()
    sharp["commence_date"] = pd.to_datetime(sharp["commence_time"]).dt.date
    candidate = sharp[(sharp["commence_date"] == game_date) &
                      ((sharp["home_team"].str.contains(home, case=False, regex=False)) |
                       (sharp["home_team"].str.upper() == home.upper()))]
    if candidate.empty:
        return None
    if "fetched_at" in candidate.columns:
        candidate = candidate.sort_values("fetched_at", ascending=False)
    return float(candidate.iloc[0]["home_prob"])


def _elo_home_prob(home: str, away: str) -> float:
    elo = _load_elo()
    eh = elo.get(home, DEFAULT_RATING)
    ea = elo.get(away, DEFAULT_RATING)
    diff = (eh + HFA) - ea
    return 1.0 / (1.0 + 10.0 ** (-diff / 400.0))


def _is_default_elo(home: str, away: str) -> bool:
    elo = _load_elo()
    return home not in elo and away not in elo


def get_live_pregame_prior(home: str, away: str, game_date: date) -> PriorResult:
    """Sharp -> Elo -> default-Elo fallback. Never returns the old 0.54 magic number."""
    sharp_prob = _try_sharp(home, away, game_date)
    if sharp_prob is not None:
        return PriorResult(home_prob=sharp_prob, source=0)

    elo_prob = _elo_home_prob(home, away)
    if _is_default_elo(home, away):
        return PriorResult(home_prob=elo_prob, source=2)
    return PriorResult(home_prob=elo_prob, source=1)
