import pandas as pd
import pytest
from datetime import date
from data.foundation.statcast_batter_aggregator import (
    aggregate_per_batter_per_date,
    _scale_to_100,
)

def _synthetic_pas():
    return pd.DataFrame([
        {"batter": 654321, "game_date": "2025-04-01", "estimated_woba_using_speedangle": 0.350, "events": "field_out"},
        {"batter": 654321, "game_date": "2025-04-01", "estimated_woba_using_speedangle": 0.500, "events": "single"},
        {"batter": 654321, "game_date": "2025-04-01", "estimated_woba_using_speedangle": None, "events": "walk"},
        {"batter": 654321, "game_date": "2025-04-02", "estimated_woba_using_speedangle": 0.420, "events": "double"},
        {"batter": 654321, "game_date": "2025-04-02", "estimated_woba_using_speedangle": 0.600, "events": "home_run"},
    ])

def test_aggregate_drops_null_xwoba_rows():
    df = _synthetic_pas()
    out = aggregate_per_batter_per_date(df)
    apr1 = out[(out.batter_id == 654321) & (out.game_date == date(2025, 4, 1))]
    assert len(apr1) == 1
    assert apr1.iloc[0]["xwoba_mean"] == pytest.approx(0.425, abs=0.001)
    assert apr1.iloc[0]["pa"] == 3
    assert apr1.iloc[0]["xwoba_pa"] == 2

def test_scale_to_100():
    assert _scale_to_100(0.320, league_avg=0.320) == pytest.approx(100.0)
    assert _scale_to_100(0.400, league_avg=0.320) == pytest.approx(125.0)
    assert _scale_to_100(0.240, league_avg=0.320) == pytest.approx(75.0)

def test_empty_returns_empty_frame():
    out = aggregate_per_batter_per_date(pd.DataFrame())
    assert out.empty
    assert list(out.columns) == ["batter_id", "game_date", "xwoba_mean", "pa", "xwoba_pa", "season"]
