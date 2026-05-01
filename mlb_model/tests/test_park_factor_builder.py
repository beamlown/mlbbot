import pandas as pd
import pytest
from data.foundation.park_factor_builder import compute_park_factors

def _synthetic_game_logs():
    rows = []
    for season in [2023, 2024]:
        for g in range(50):
            rows.append({"season": season, "park_id": "neutral", "home_runs": 5, "away_runs": 4})
        for g in range(50):
            rows.append({"season": season, "park_id": "coors", "home_runs": 6, "away_runs": 5})
        for g in range(50):
            rows.append({"season": season, "park_id": "petco", "home_runs": 4, "away_runs": 3})
    return pd.DataFrame(rows)

def test_neutral_park_factor_close_to_one():
    df = _synthetic_game_logs()
    out = compute_park_factors(df, rolling_years=2)
    neutral_2024 = out[(out.park_id == "neutral") & (out.season == 2024)].iloc[0]
    assert 0.95 < neutral_2024.run_factor < 1.05

def test_hitter_park_above_one():
    df = _synthetic_game_logs()
    out = compute_park_factors(df, rolling_years=2)
    coors_2024 = out[(out.park_id == "coors") & (out.season == 2024)].iloc[0]
    assert coors_2024.run_factor > 1.10

def test_pitcher_park_below_one():
    df = _synthetic_game_logs()
    out = compute_park_factors(df, rolling_years=2)
    petco_2024 = out[(out.park_id == "petco") & (out.season == 2024)].iloc[0]
    assert petco_2024.run_factor < 0.90

def test_first_season_uses_only_available_history():
    df = _synthetic_game_logs()
    df_one_season = df[df.season == 2023]
    out = compute_park_factors(df_one_season, rolling_years=3)
    assert len(out) == 3   # one row per park
