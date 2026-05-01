from datetime import date
import pandas as pd
import pytest
from sports.mlb.reliever_quality_live import (
    lookup_reliever_quality, _set_test_table, RelieverQuality,
)

@pytest.fixture(autouse=True)
def reset():
    yield
    _set_test_table(None)

def test_lookup_known():
    tbl = pd.DataFrame([{
        "pitcher_id": "R1", "as_of_date": date(2025, 7, 1),
        "reliever_quality": 85.0, "n_outings_std": 40,
    }])
    _set_test_table(tbl)
    q = lookup_reliever_quality("R1", date(2025, 7, 1))
    assert q.reliever_quality == pytest.approx(85.0)
    assert q.imputed is False

def test_unknown_imputes_100():
    _set_test_table(pd.DataFrame(columns=["pitcher_id", "as_of_date", "reliever_quality", "n_outings_std"]))
    q = lookup_reliever_quality("unknown", date(2025, 7, 1))
    assert q.reliever_quality == 100.0
    assert q.imputed is True

def test_falls_back_to_prior_date():
    tbl = pd.DataFrame([{
        "pitcher_id": "R1", "as_of_date": date(2025, 6, 1),
        "reliever_quality": 90.0, "n_outings_std": 20,
    }])
    _set_test_table(tbl)
    q = lookup_reliever_quality("R1", date(2025, 7, 1))
    assert q.reliever_quality == pytest.approx(90.0)
    assert q.imputed is False
