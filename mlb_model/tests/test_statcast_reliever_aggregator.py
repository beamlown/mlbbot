import pandas as pd
import pytest
from data.foundation.statcast_reliever_aggregator import aggregate_reliever_per_game

def _outs_events(n):
    return [{"pitcher": 99, "game_pk": 1, "game_date": "2025-04-01", "events": "field_out"}] * n

def test_filters_out_starters():
    """Starters (>= 4 IP = >= 12 outs) should be excluded."""
    rows = _outs_events(13) + [{"pitcher": 99, "game_pk": 1, "game_date": "2025-04-01", "events": "strikeout"}]
    df = pd.DataFrame(rows)
    out = aggregate_reliever_per_game(df)
    assert out.empty

def test_keeps_short_relief():
    """2 IP (6 outs) is a relief outing."""
    rows = _outs_events(5) + [{"pitcher": 99, "game_pk": 1, "game_date": "2025-04-01", "events": "walk"}]
    df = pd.DataFrame(rows)
    out = aggregate_reliever_per_game(df)
    assert len(out) == 1
    assert out.iloc[0]["ip"] < 4.0
    assert out.iloc[0]["bb"] == 1

def test_empty_returns_empty():
    out = aggregate_reliever_per_game(pd.DataFrame())
    assert out.empty
