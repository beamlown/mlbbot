from datetime import date
import pandas as pd
import pytest
from sports.mlb.batter_quality_live import (
    lookup_batter_xwoba, lookup_batters_avg_xwoba, _set_test_table, BatterQuality
)

@pytest.fixture(autouse=True)
def reset():
    yield
    _set_test_table(None)

def _table():
    return pd.DataFrame([
        {"batter_id": "p1", "as_of_date": date(2025, 7, 1), "batter_xwoba": 120.0, "n_pa_std": 250},
        {"batter_id": "p2", "as_of_date": date(2025, 7, 1), "batter_xwoba": 95.0, "n_pa_std": 100},
    ])

def test_lookup_known_batter():
    _set_test_table(_table())
    q = lookup_batter_xwoba("p1", date(2025, 7, 1))
    assert q.batter_xwoba == pytest.approx(120.0)
    assert q.imputed is False

def test_lookup_unknown_batter_imputes_100():
    _set_test_table(pd.DataFrame(columns=["batter_id", "as_of_date", "batter_xwoba", "n_pa_std"]))
    q = lookup_batter_xwoba("rookie", date(2025, 7, 1))
    assert q.batter_xwoba == 100.0
    assert q.imputed is True

def test_lookup_avg_aggregates_known_and_imputes_unknown():
    _set_test_table(_table())
    avg = lookup_batters_avg_xwoba(["p1", "p2", "rookie"], date(2025, 7, 1))
    # 120, 95, 100 -> mean = 105
    assert avg == pytest.approx(105.0, abs=0.1)

def test_lookup_avg_empty_list_returns_100():
    _set_test_table(_table())
    assert lookup_batters_avg_xwoba([], date(2025, 7, 1)) == 100.0
