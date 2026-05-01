"""
End-to-end smoke test with synthetic 100-game season.

Verifies:
  - park factor builder runs and writes parquet
  - pitcher quality builder runs point-in-time
  - both produce non-empty parquets
"""
import tempfile
from datetime import date, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from data.foundation.park_factor_builder import compute_park_factors
from data.foundation.pitcher_quality_builder import compute_pitcher_quality_pointtime


def test_synthetic_pipeline_produces_parquets(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("data/features").mkdir(parents=True, exist_ok=True)

    # Fake game logs for park factors
    game_logs = pd.DataFrame([
        {"season": 2024, "park_id": "p1", "home_runs": 5, "away_runs": 4}
        for _ in range(50)
    ] + [
        {"season": 2024, "park_id": "p2", "home_runs": 3, "away_runs": 3}
        for _ in range(50)
    ])
    pf = compute_park_factors(game_logs, rolling_years=1)
    pf.to_parquet("data/features/park_factors.parquet", index=False)

    # Fake pitcher starts
    starts = pd.DataFrame([{
        "pitcher_id": f"pitcher_{i % 10}",
        "game_date": (date(2024, 4, 1) + timedelta(days=i % 90)),
        "ip": 6.0,
        "fip": 4.0 + (i % 5 - 2) * 0.3,
        "season": 2024,
    } for i in range(100)])
    pq = compute_pitcher_quality_pointtime(starts, snapshot_dates=[date(2024, 7, 1)])
    pq.to_parquet("data/features/pitcher_quality.parquet", index=False)

    assert pd.read_parquet("data/features/park_factors.parquet").shape[0] > 0
    assert pd.read_parquet("data/features/pitcher_quality.parquet").shape[0] > 0


def test_statcast_path_produces_pitcher_quality(tmp_path, monkeypatch):
    """End-to-end: Statcast pitches -> aggregate -> pitcher_quality_pointtime."""
    monkeypatch.chdir(tmp_path)
    Path("data/features").mkdir(parents=True, exist_ok=True)

    from data.foundation.statcast_pitcher_aggregator import aggregate_per_pitcher_per_game
    from data.foundation.pitcher_quality_builder import compute_pitcher_quality_pointtime

    rows = []
    for start_idx in range(10):
        for out_idx in range(18):   # 18 outs = 6 IP per start
            rows.append({
                "pitcher": 12345,
                "game_pk": 1000 + start_idx,
                "game_date": (date(2024, 4, 1) + timedelta(days=start_idx * 7)),
                "events": "field_out",
            })
        rows.append({
            "pitcher": 12345,
            "game_pk": 1000 + start_idx,
            "game_date": (date(2024, 4, 1) + timedelta(days=start_idx * 7)),
            "events": "strikeout",
        })

    pitches = pd.DataFrame(rows)
    starts = aggregate_per_pitcher_per_game(pitches)
    assert len(starts) == 10   # one row per start
    starts["pitcher_id"] = starts["pitcher_id"].astype(str)

    pq = compute_pitcher_quality_pointtime(
        starts[["pitcher_id", "game_date", "ip", "fip", "season"]],
        snapshot_dates=[date(2024, 7, 1)],
    )
    assert len(pq) == 1
    assert pq.iloc[0]["pitcher_id"] == "12345"
    # 6 IP per start; FIP = (0+0-2*1)/6 + 3.2 = 2.867 -> sp_quality < 100 (below average → better)
    assert pq.iloc[0]["sp_quality"] < 100.0


def test_batter_aggregator_path(tmp_path, monkeypatch):
    """End-to-end: Statcast pitches -> batter aggregator -> batter quality table."""
    monkeypatch.chdir(tmp_path)
    Path("data/features").mkdir(parents=True, exist_ok=True)

    from data.foundation.statcast_batter_aggregator import aggregate_per_batter_per_date
    from data.foundation.batter_quality_builder import compute_batter_quality_pointtime

    rows = []
    for i in range(100):
        rows.append({
            "batter": 654321,
            "game_date": date(2024, 4, 1) + timedelta(days=i % 90),
            "estimated_woba_using_speedangle": 0.380,
            "events": "field_out",
        })
    pitches = pd.DataFrame(rows)
    history = aggregate_per_batter_per_date(pitches)
    history["batter_id"] = history["batter_id"].astype(str)
    bq = compute_batter_quality_pointtime(history, snapshot_dates=[date(2024, 7, 1)])
    assert len(bq) == 1
    assert bq.iloc[0]["batter_id"] == "654321"
    # Above-avg hitter → batter_xwoba > 100
    assert bq.iloc[0]["batter_xwoba"] > 100.0


def test_reliever_aggregator_path(tmp_path, monkeypatch):
    """End-to-end: Statcast pitches -> reliever aggregator -> reliever_quality table."""
    monkeypatch.chdir(tmp_path)
    Path("data/features").mkdir(parents=True, exist_ok=True)

    from data.foundation.statcast_reliever_aggregator import aggregate_reliever_per_game
    from data.foundation.reliever_quality_builder import compute_reliever_quality_pointtime

    # One pitcher with 10 short relief outings (~1 IP each, good FIP)
    rows = []
    for start_idx in range(10):
        rows.append({"pitcher": 77777,
                     "game_pk": 2000 + start_idx,
                     "game_date": date(2024, 5, 1) + timedelta(days=start_idx * 2),
                     "events": "strikeout"})
        rows.append({"pitcher": 77777,
                     "game_pk": 2000 + start_idx,
                     "game_date": date(2024, 5, 1) + timedelta(days=start_idx * 2),
                     "events": "field_out"})
        rows.append({"pitcher": 77777,
                     "game_pk": 2000 + start_idx,
                     "game_date": date(2024, 5, 1) + timedelta(days=start_idx * 2),
                     "events": "field_out"})

    pitches = pd.DataFrame(rows)
    starts = aggregate_reliever_per_game(pitches)
    assert len(starts) == 10
    assert all(starts["ip"] < 4.0)
    starts["pitcher_id"] = starts["pitcher_id"].astype(str)

    rq = compute_reliever_quality_pointtime(
        starts[["pitcher_id", "game_date", "ip", "fip", "season"]],
        snapshot_dates=[date(2024, 7, 1)],
    )
    assert len(rq) == 1
    assert rq.iloc[0]["pitcher_id"] == "77777"
    # Lots of Ks per walk → FIP < league avg → reliever_quality < 100
    assert rq.iloc[0]["reliever_quality"] < 100.0
