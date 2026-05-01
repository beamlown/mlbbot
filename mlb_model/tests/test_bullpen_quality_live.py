from datetime import date
import pandas as pd
import pytest
from sports.mlb.bullpen_quality_live import lookup_bullpen_quality, _set_test_table

@pytest.fixture(autouse=True)
def reset():
    yield
    _set_test_table(None)

def test_lookup_known():
    tbl = pd.DataFrame([{
        "team": "LAA", "as_of_date": date(2025, 7, 1),
        "bullpen_avg_quality": 88.0, "n_relievers": 8,
    }])
    _set_test_table(tbl)
    q = lookup_bullpen_quality("LAA", date(2025, 7, 1))
    assert q == pytest.approx(88.0)

def test_lookup_unknown_returns_100():
    _set_test_table(pd.DataFrame(columns=["team", "as_of_date", "bullpen_avg_quality", "n_relievers"]))
    assert lookup_bullpen_quality("XXX", date(2025, 7, 1)) == 100.0

def test_fallback_to_prior_date():
    tbl = pd.DataFrame([{
        "team": "LAA", "as_of_date": date(2025, 6, 1),
        "bullpen_avg_quality": 95.0, "n_relievers": 8,
    }])
    _set_test_table(tbl)
    assert lookup_bullpen_quality("LAA", date(2025, 7, 1)) == pytest.approx(95.0)
