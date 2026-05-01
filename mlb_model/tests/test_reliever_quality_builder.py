import pandas as pd
import pytest
from datetime import date
from data.foundation.reliever_quality_builder import (
    compute_reliever_quality_pointtime,
)

def _synthetic_relief():
    """Reliever R1 with 20 relief appearances in 2024, FIP 3.0 (better than league)."""
    rows = []
    for i in range(20):
        rows.append({
            "pitcher_id": "R1",
            "game_date": date(2024, 4, 1) + pd.Timedelta(days=i * 5).to_pytimedelta(),
            "ip": 1.0,
            "fip": 3.0,
            "season": 2024,
        })
    return pd.DataFrame(rows)

def test_pre_debut_returns_no_row():
    h = _synthetic_relief()
    out = compute_reliever_quality_pointtime(h, snapshot_dates=[date(2024, 3, 1)])
    assert "R1" not in out.pitcher_id.values

def test_midseason_below_average_fip_yields_good_quality():
    h = _synthetic_relief()
    out = compute_reliever_quality_pointtime(h, snapshot_dates=[date(2024, 9, 1)])
    r = out[out.pitcher_id == "R1"].iloc[0]
    # FIP 3.0 vs league 4.0 → regressed somewhat toward 100 but should still be below 100
    assert r.reliever_quality < 100
    assert r.n_outings_std > 0
