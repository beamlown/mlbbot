import pandas as pd
import pytest
from datetime import date
from data.foundation.pitcher_quality_builder import (
    compute_pitcher_quality_pointtime,
    _hybrid_fip_minus,
    _recent_form_delta,
)

LEAGUE_FIP = 4.00

def _synthetic_starts():
    rows = []
    for i, d in enumerate(pd.date_range("2024-04-01", periods=5, freq="7D")):
        rows.append({"pitcher_id": "A", "game_date": d.date(), "ip": 6.0, "fip": 3.50, "season": 2024})
    for i, d in enumerate(pd.date_range("2025-04-01", periods=5, freq="7D")):
        rows.append({"pitcher_id": "A", "game_date": d.date(), "ip": 6.0, "fip": 3.00, "season": 2025})
    return pd.DataFrame(rows)

def test_no_leakage_query_before_first_start_returns_imputed():
    starts = _synthetic_starts()
    out = compute_pitcher_quality_pointtime(starts, league_fip=LEAGUE_FIP)
    pre_first = out[(out.pitcher_id == "A") & (out.as_of_date == date(2024, 3, 1))]
    assert len(pre_first) == 1
    # No prior data: hybrid should equal league mean (100)
    assert pre_first.iloc[0].sp_quality == pytest.approx(100.0, abs=1.0)

def test_no_leakage_mid_2025_only_uses_pre_date_starts():
    starts = _synthetic_starts()
    out = compute_pitcher_quality_pointtime(starts, league_fip=LEAGUE_FIP)
    midseason = out[(out.pitcher_id == "A") & (out.as_of_date == date(2025, 4, 15))]
    assert len(midseason) == 1
    # Hybrid: 0.4 * (2024 FIP=3.50) + 0.6 * (current STD = 3.00)
    expected_hybrid = 0.4 * 3.50 + 0.6 * 3.00
    assert midseason.iloc[0].sp_quality == pytest.approx((expected_hybrid / LEAGUE_FIP) * 100, abs=1.5)

def test_recent_form_positive_when_recent_better_than_baseline():
    delta = _recent_form_delta(baseline_fip=4.0, recent_fip=3.0)
    assert delta > 0

def test_recent_form_negative_when_recent_worse():
    delta = _recent_form_delta(baseline_fip=3.0, recent_fip=4.5)
    assert delta < 0
