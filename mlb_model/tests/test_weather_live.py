import pandas as pd
import pytest
from datetime import datetime, timezone
from sports.mlb.weather_live import (
    lookup_weather_for_game, _set_test_table, WeatherRow,
)

@pytest.fixture(autouse=True)
def reset():
    yield
    _set_test_table(None)

def test_lookup_known_game_returns_cached():
    tbl = pd.DataFrame([{
        "game_id": "g1", "park_id": "DEN02", "temp_f": 82.0,
        "wind_mph": 8.0, "wind_from_deg": 180.0,
        "wind_out_mph": -8.0, "is_roof_closed": 0,
    }])
    _set_test_table(tbl)
    w = lookup_weather_for_game("g1")
    assert w.temp_f == pytest.approx(82.0)
    assert w.wind_out_mph == pytest.approx(-8.0)
    assert w.is_roof_closed is False

def test_lookup_unknown_game_returns_neutral():
    _set_test_table(pd.DataFrame(columns=[
        "game_id", "park_id", "temp_f", "wind_mph", "wind_from_deg",
        "wind_out_mph", "is_roof_closed",
    ]))
    w = lookup_weather_for_game("unknown")
    assert w.temp_f == 70.0
    assert w.wind_out_mph == 0.0
    assert w.is_roof_closed is True
