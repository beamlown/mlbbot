import pandas as pd
import pytest
from datetime import date
from data.foundation.batter_quality_builder import (
    compute_batter_quality_pointtime,
    _hybrid_xwoba,
)

def _synthetic_pa_history():
    """Batter A: 200 PA in 2024 (xwoba=0.350), 50 PA in 2025 (xwoba=0.400)."""
    rows = []
    for i in range(200):
        rows.append({
            "batter_id": "A",
            "game_date": date(2024, 4, 1) + pd.Timedelta(days=i % 180).to_pytimedelta(),
            "xwoba_mean": 0.350,
            "pa": 1,
            "xwoba_pa": 1,
            "season": 2024,
        })
    # Enough 2025 PAs before May 1 snapshot that sample clears regression floor.
    for i in range(500):
        rows.append({
            "batter_id": "A",
            "game_date": date(2025, 4, 1) + pd.Timedelta(days=i % 29).to_pytimedelta(),
            "xwoba_mean": 0.400,
            "pa": 1,
            "xwoba_pa": 1,
            "season": 2025,
        })
    return pd.DataFrame(rows)

def test_hybrid_uses_only_pre_date_data():
    h = _synthetic_pa_history()
    out = compute_batter_quality_pointtime(h, snapshot_dates=[date(2024, 3, 1)])
    # Pre-2024-04-01 → no history at all → no row emitted (caller imputes)
    assert out.empty or "A" not in out.batter_id.values

def test_hybrid_blends_prior_season_with_current_std():
    h = _synthetic_pa_history()
    out = compute_batter_quality_pointtime(h, snapshot_dates=[date(2025, 5, 1)])
    a = out[out.batter_id == "A"].iloc[0]
    # Hybrid: 0.6 * current_xwoba + 0.4 * prior_xwoba, regressed toward league (0.320)
    # Expected to be > 100 since both periods are above league avg
    assert a.batter_xwoba > 105
    assert a.batter_xwoba < 125

def test_unknown_batter_returns_no_row():
    h = _synthetic_pa_history()
    out = compute_batter_quality_pointtime(h, snapshot_dates=[date(2025, 5, 1)])
    assert "Z" not in out.batter_id.values

def test_hybrid_xwoba_pure_compute():
    # prior=0.350, current=0.400, std_pa=50, league=0.320, regression_pa=200
    # Hybrid raw = 0.6*0.400 + 0.4*0.350 = 0.380
    # weight = 50/(50+200) = 0.20; regressed = 0.20*0.380 + 0.80*0.320 = 0.332
    # Scale: 0.332/0.320 * 100 = 103.75
    val = _hybrid_xwoba(prior_xwoba=0.350, std_xwoba=0.400, std_pa=50,
                        league_xwoba=0.320, regression_pa=200)
    assert val == pytest.approx(103.75, abs=0.5)
