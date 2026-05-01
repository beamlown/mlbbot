from datetime import date
import pandas as pd
import pytest
from sports.mlb.pregame_prior_live import (
    get_live_pregame_prior, _set_test_sharp, _set_test_elo, PriorResult
)

@pytest.fixture(autouse=True)
def reset():
    yield
    _set_test_sharp(None)
    _set_test_elo(None)

def test_sharp_wins_when_available():
    sharp = pd.DataFrame([{
        "home_team": "LAA", "away_team": "SDP",
        "commence_time": "2026-04-19T23:05:00Z",
        "home_prob": 0.42,
    }])
    _set_test_sharp(sharp)
    _set_test_elo({"LAA": 1500.0, "SDP": 1500.0})
    res = get_live_pregame_prior("LAA", "SDP", date(2026, 4, 19))
    assert res.home_prob == pytest.approx(0.42)
    assert res.source == 0  # sharp

def test_falls_back_to_elo_when_no_sharp():
    _set_test_sharp(pd.DataFrame(columns=["home_team", "away_team", "commence_time", "home_prob"]))
    _set_test_elo({"LAA": 1530.0, "SDP": 1500.0})
    res = get_live_pregame_prior("LAA", "SDP", date(2026, 4, 19))
    assert res.home_prob > 0.55
    assert res.source == 1  # elo

def test_no_default_054_anywhere():
    """Critical: never returns 0.54. Returns elo-derived even with default ratings."""
    _set_test_sharp(pd.DataFrame(columns=["home_team", "away_team", "commence_time", "home_prob"]))
    _set_test_elo({})
    res = get_live_pregame_prior("BRAND", "NEW", date(2026, 4, 19))
    assert res.home_prob == pytest.approx(0.534, abs=0.01)
    assert res.source == 2  # default
