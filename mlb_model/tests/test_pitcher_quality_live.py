from datetime import date
import pandas as pd
import pytest
from sports.mlb.pitcher_quality_live import lookup_pitcher_quality, _set_test_table

@pytest.fixture(autouse=True)
def reset():
    yield
    _set_test_table(None)

def test_known_pitcher():
    table = pd.DataFrame([
        {"pitcher_id": "p1", "as_of_date": date(2025, 7, 1),
         "sp_quality": 85.0, "sp_recent_form": 0.5, "n_starts_std": 18},
    ])
    _set_test_table(table)
    q = lookup_pitcher_quality("p1", date(2025, 7, 1))
    assert q.sp_quality == pytest.approx(85.0)
    assert q.sp_recent_form == pytest.approx(0.5)
    assert q.imputed is False

def test_unknown_pitcher_imputes_league_mean():
    _set_test_table(pd.DataFrame(columns=["pitcher_id", "as_of_date",
                                          "sp_quality", "sp_recent_form", "n_starts_std"]))
    q = lookup_pitcher_quality("rookie_unknown", date(2025, 7, 1))
    assert q.sp_quality == 100.0
    assert q.sp_recent_form == 0.0
    assert q.imputed is True

def test_falls_back_to_most_recent_prior_date():
    table = pd.DataFrame([
        {"pitcher_id": "p1", "as_of_date": date(2025, 6, 1),
         "sp_quality": 90.0, "sp_recent_form": 0.0, "n_starts_std": 10},
    ])
    _set_test_table(table)
    q = lookup_pitcher_quality("p1", date(2025, 7, 1))
    assert q.sp_quality == pytest.approx(90.0)
    assert q.imputed is False
