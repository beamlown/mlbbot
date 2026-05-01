import pandas as pd
import pytest
from sports.mlb.park_factor_live import lookup_park_factor, _set_test_table

@pytest.fixture(autouse=True)
def reset_table():
    yield
    _set_test_table(None)

def test_lookup_known_park():
    table = pd.DataFrame([
        {"season": 2025, "park_id": "coors", "run_factor": 1.12, "n_games": 243},
        {"season": 2025, "park_id": "petco", "run_factor": 0.91, "n_games": 243},
    ])
    _set_test_table(table)
    assert lookup_park_factor("coors", 2025) == pytest.approx(1.12)
    assert lookup_park_factor("petco", 2025) == pytest.approx(0.91)

def test_lookup_unknown_park_returns_neutral():
    _set_test_table(pd.DataFrame(columns=["season", "park_id", "run_factor", "n_games"]))
    assert lookup_park_factor("brand_new_stadium", 2025) == 1.0

def test_lookup_falls_back_to_most_recent_season():
    table = pd.DataFrame([
        {"season": 2024, "park_id": "coors", "run_factor": 1.12, "n_games": 243},
    ])
    _set_test_table(table)
    assert lookup_park_factor("coors", 2025) == pytest.approx(1.12)
