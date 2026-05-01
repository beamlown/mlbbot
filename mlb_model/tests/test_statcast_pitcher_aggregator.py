import pandas as pd
import pytest
from datetime import date
from data.foundation.statcast_pitcher_aggregator import (
    aggregate_per_pitcher_per_game,
    _compute_fip,
    _OUT_EVENTS,
    _K_EVENTS,
    _BB_EVENTS,
)

def _synthetic_pitches():
    """Pitcher 12345 throws a single game: 3 outs, 1 K, 1 BB, 1 HR."""
    rows = [
        {"pitcher": 12345, "game_pk": 999, "game_date": "2025-04-01", "events": "field_out"},
        {"pitcher": 12345, "game_pk": 999, "game_date": "2025-04-01", "events": "strikeout"},
        {"pitcher": 12345, "game_pk": 999, "game_date": "2025-04-01", "events": "walk"},
        {"pitcher": 12345, "game_pk": 999, "game_date": "2025-04-01", "events": "home_run"},
        {"pitcher": 12345, "game_pk": 999, "game_date": "2025-04-01", "events": "force_out"},
    ]
    return pd.DataFrame(rows)

def test_fip_formula():
    # IP=1.0, K=1, BB=1, HR=1 → (13*1 + 3*1 - 2*1) / 1.0 + 3.2 = 17.2
    assert _compute_fip(ip=1.0, hr=1, bb=1, k=1) == pytest.approx(17.2)

def test_fip_zero_ip_returns_nan():
    import math
    assert math.isnan(_compute_fip(ip=0.0, hr=0, bb=0, k=0))

def test_aggregate_single_pitcher_single_game():
    df = _synthetic_pitches()
    out = aggregate_per_pitcher_per_game(df)
    assert len(out) == 1
    r = out.iloc[0]
    assert r["pitcher_id"] == 12345
    assert r["ip"] == pytest.approx(3 / 3)   # 3 outs = 1 inning
    assert r["k"] == 1
    assert r["bb"] == 1
    assert r["hr"] == 1
    assert r["fip"] == pytest.approx(17.2, abs=0.01)
    assert r["season"] == 2025

def test_aggregate_skips_pitchers_with_zero_ip():
    """A relief pitcher who recorded no outs should still appear, with fip=NaN."""
    df = pd.DataFrame([
        {"pitcher": 99, "game_pk": 1, "game_date": "2025-04-01", "events": "single"},
        {"pitcher": 99, "game_pk": 1, "game_date": "2025-04-01", "events": "walk"},
    ])
    out = aggregate_per_pitcher_per_game(df)
    assert len(out) == 1
    import math
    assert math.isnan(out.iloc[0]["fip"])
    assert out.iloc[0]["ip"] == 0
