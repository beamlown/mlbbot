import pandas as pd
import pytest
from datetime import date, timedelta
from data.foundation.bullpen_aggregator import compute_bullpen_quality

def _synthetic_team_relief():
    """Team LAA with 3 relievers in last 30 days."""
    rows = []
    for rid, fip in [("A", 2.5), ("B", 3.5), ("C", 5.0)]:
        for i in range(15):
            rows.append({
                "pitcher_id": rid,
                "team": "LAA",
                "game_date": date(2025, 6, 1) + timedelta(days=i),
                "ip": 1.0,
                "fip": fip,
            })
    return pd.DataFrame(rows)

def test_bullpen_weighted_avg():
    h = _synthetic_team_relief()
    out = compute_bullpen_quality(h, as_of=date(2025, 7, 1), window_days=30)
    row = out[out.team == "LAA"].iloc[0]
    # 3 relievers each with 15 IP @ FIP {2.5, 3.5, 5.0}
    # Weighted avg = (15*2.5 + 15*3.5 + 15*5.0) / 45 = 3.6667
    # FIP- = 3.6667/4.0 * 100 = 91.67
    assert 88 < row.bullpen_avg_quality < 95
    assert row.n_relievers == 3

def test_empty_returns_empty():
    out = compute_bullpen_quality(pd.DataFrame(), as_of=date(2025, 7, 1))
    assert out.empty
