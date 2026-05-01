# MLB Model Signal Quality #2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 5 batter-quality features (current batter xwOBA, next-3 avg, lineup avg, platoon advantage, leverage interaction) to the win-prob model. Feature count grows 30 → 35.

**Architecture:** Mirrors the pitcher quality pattern from #1+#1.5. Statcast pitch data → per-PA xwOBA aggregation → point-in-time hybrid table keyed on MLBAM batter IDs. Live lookup via MLB Stats API for current batter + lineup. Audit framework decides which features promote.

**Tech Stack:** Python 3.11, pandas/pyarrow, pytest, MLB Stats API (statsapi.mlb.com), Windows Task Scheduler.

**Spec:** `docs/superpowers/specs/2026-04-19-mlb-model-signal-quality-2-design.md`

---

## File Map

### New
| Path | Responsibility |
|---|---|
| `data/foundation/statcast_batter_aggregator.py` | Aggregate Statcast pitches → per-PA xwOBA per batter (mirror of pitcher aggregator) |
| `data/foundation/batter_quality_builder.py` | Point-in-time hybrid xwOBA per `(batter_id, as_of_date)` |
| `sports/mlb/batter_quality_live.py` | `(batter_id, date) → xwOBA` live lookup |
| `sports/mlb/lineup_live.py` | MLB Stats API fetch of current batter, lineups, handedness |
| `scripts/refresh_batter_quality_daily.py` | Daily incremental from Statcast |
| `scripts/cron/run_refresh_batter_quality_daily.bat` | Windows wrapper |
| `tests/test_statcast_batter_aggregator.py` | Unit |
| `tests/test_batter_quality_builder.py` | Unit (point-in-time leak guard) |
| `tests/test_batter_quality_live.py` | Unit |
| `tests/test_lineup_live.py` | Unit (mocked HTTP) |

### Modified
| Path | Change |
|---|---|
| `data/state_snapshot_builder.py` | Emit 7 new columns: `batter_id`, `batter_stand`, `home_pitcher_p_throws`, `away_pitcher_p_throws`, `home_lineup_ids`, `away_lineup_ids`, `current_lineup_position` |
| `data/feature_store.py` | Extend FEATURE_COLUMNS (30→35) + enrich with 5 new batter features |
| `sports/mlb/winprob_inference.py` | `_build_feature_vector` accepts `phase2_extras`; vector grows to 35 |
| `integration/recommendation_api.py` | Build phase2_extras from live lineup + batter quality lookup; pass to inference; surface in reasons |
| `core/selfcheck.py` | `EXPECTED_FEATURE_COUNT = 35` |
| `models/audit_features.py` | Add `PHASE2_NEW_FEATURES` constant |
| `scripts/cron/install_scheduled_tasks.bat` | Add 4th task `mlb-batter-quality-daily` @ 08:30 |
| `docs/runbook.md` | Document new cron task |
| `tests/integration/test_full_pipeline.py` | Extend with batter aggregator path |

---

## Task 1: Statcast batter aggregator

**Files:**
- Create: `C:/Users/johnny/Desktop/mlb_model/data/foundation/statcast_batter_aggregator.py`
- Create: `C:/Users/johnny/Desktop/mlb_model/tests/test_statcast_batter_aggregator.py`

- [ ] **Step 1: Write failing test**

`tests/test_statcast_batter_aggregator.py`:

```python
import pandas as pd
import pytest
from datetime import date
from data.foundation.statcast_batter_aggregator import (
    aggregate_per_batter_per_date,
    _scale_to_100,
)

def _synthetic_pas():
    """Batter 654321 has 5 PAs across 2 dates with known xwoba values."""
    return pd.DataFrame([
        {"batter": 654321, "game_date": "2025-04-01", "estimated_woba_using_speedangle": 0.350, "events": "field_out"},
        {"batter": 654321, "game_date": "2025-04-01", "estimated_woba_using_speedangle": 0.500, "events": "single"},
        {"batter": 654321, "game_date": "2025-04-01", "estimated_woba_using_speedangle": None, "events": "walk"},  # walks have no xwoba
        {"batter": 654321, "game_date": "2025-04-02", "estimated_woba_using_speedangle": 0.420, "events": "double"},
        {"batter": 654321, "game_date": "2025-04-02", "estimated_woba_using_speedangle": 0.600, "events": "home_run"},
    ])

def test_aggregate_drops_null_xwoba_rows():
    df = _synthetic_pas()
    out = aggregate_per_batter_per_date(df)
    # walk row (xwoba=None) should not contribute to mean but should count in pa
    apr1 = out[(out.batter_id == 654321) & (out.game_date == date(2025, 4, 1))]
    assert len(apr1) == 1
    # mean of 0.350 and 0.500 = 0.425
    assert apr1.iloc[0]["xwoba_mean"] == pytest.approx(0.425, abs=0.001)
    assert apr1.iloc[0]["pa"] == 3   # 3 plate appearances total
    assert apr1.iloc[0]["xwoba_pa"] == 2  # 2 with batted-ball xwoba

def test_scale_to_100():
    # league avg xwoba = 0.320 baseline
    assert _scale_to_100(0.320, league_avg=0.320) == pytest.approx(100.0)
    assert _scale_to_100(0.400, league_avg=0.320) == pytest.approx(125.0)
    assert _scale_to_100(0.240, league_avg=0.320) == pytest.approx(75.0)

def test_empty_returns_empty_frame():
    out = aggregate_per_batter_per_date(pd.DataFrame())
    assert out.empty
    assert list(out.columns) == ["batter_id", "game_date", "xwoba_mean", "pa", "xwoba_pa", "season"]
```

- [ ] **Step 2: Run test, confirm it fails**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_statcast_batter_aggregator.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `data/foundation/statcast_batter_aggregator.py`**

```python
"""
data/foundation/statcast_batter_aggregator.py

Aggregate Statcast pitch data into per-(batter_id, game_date) xwOBA rows.
Uses estimated_woba_using_speedangle (xwOBA) — Statcast's predicted wOBA from
launch angle + exit velocity. Walks/HBP have no xwoba (no batted ball), so
they're counted in PA but not in the xwoba_mean.

Output schema:
    batter_id (int), game_date (date), xwoba_mean (float),
    pa (int), xwoba_pa (int), season (int)
"""
from __future__ import annotations
import logging
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

LEAGUE_AVG_XWOBA = 0.320  # rough MLB-wide baseline; refined per-season in builder


def _scale_to_100(xwoba: float, league_avg: float = LEAGUE_AVG_XWOBA) -> float:
    """Scale raw xwoba to 100-centered (>100 = above avg, lower = below)."""
    if league_avg <= 0:
        return 100.0
    return (xwoba / league_avg) * 100.0


def aggregate_per_batter_per_date(pitches: pd.DataFrame) -> pd.DataFrame:
    """
    pitches columns: batter (int MLBAM), game_date, estimated_woba_using_speedangle,
                     events
    Returns one row per (batter, date) with mean xwoba over batted-ball PAs +
    raw PA count. Rows where events is null are pre-PA-end pitches and ignored.
    """
    cols = ["batter_id", "game_date", "xwoba_mean", "pa", "xwoba_pa", "season"]
    if pitches.empty:
        return pd.DataFrame(columns=cols)

    df = pitches.copy()
    df = df.dropna(subset=["batter", "events"])
    if df.empty:
        return pd.DataFrame(columns=cols)

    # Each event row = 1 PA (regardless of xwoba presence)
    df["batter"] = df["batter"].astype(int)
    df["xwoba"] = pd.to_numeric(df.get("estimated_woba_using_speedangle"), errors="coerce")

    # Group: count PAs, mean xwoba over rows where xwoba is not null
    agg = df.groupby(["batter", "game_date"], dropna=False).agg(
        pa=("events", "count"),
        xwoba_mean=("xwoba", "mean"),
        xwoba_pa=("xwoba", lambda s: int(s.notna().sum())),
    ).reset_index()

    agg = agg.rename(columns={"batter": "batter_id"})
    agg["game_date"] = pd.to_datetime(agg["game_date"]).dt.date
    agg["season"] = pd.Series([d.year for d in agg["game_date"]])
    return agg[cols]


def aggregate_from_statcast_dir(statcast_dir: Path = Path("data/raw/statcast"),
                                seasons: list[int] | None = None) -> pd.DataFrame:
    """Read all Statcast monthly parquets, aggregate, return combined DataFrame.

    Filters by season FIRST (cheap), then reads. Skips empty parquets.
    """
    import pyarrow.parquet as pq
    parquets = sorted(statcast_dir.glob("*.parquet"))
    if not parquets:
        raise FileNotFoundError(f"No Statcast parquets in {statcast_dir}")
    cols_needed = ["batter", "game_date", "events", "estimated_woba_using_speedangle"]
    frames = []
    for p in parquets:
        if seasons is not None:
            yr = None
            for tok in p.stem.replace("-", "_").split("_"):
                if tok.isdigit() and len(tok) == 4:
                    yr = int(tok)
                    break
            if yr is not None and yr not in seasons:
                continue
        try:
            schema_cols = pq.read_schema(p).names
        except Exception as e:
            logger.warning("skipping unreadable parquet %s: %s", p.name, e)
            continue
        if "batter" not in schema_cols:
            logger.info("skipping empty/incomplete parquet %s", p.name)
            continue
        df = pd.read_parquet(p, columns=cols_needed)
        if df.empty:
            continue
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["batter_id", "game_date", "xwoba_mean",
                                     "pa", "xwoba_pa", "season"])
    return aggregate_per_batter_per_date(pd.concat(frames, ignore_index=True))
```

- [ ] **Step 4: Run tests (3/3 PASSED)**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_statcast_batter_aggregator.py -v
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/data/foundation/statcast_batter_aggregator.py mlb_model/tests/test_statcast_batter_aggregator.py && git commit -m "mlb_model: add Statcast batter aggregator (per-date xwOBA) (#2)"
```

---

## Task 2: Point-in-time batter quality builder

**Files:**
- Create: `C:/Users/johnny/Desktop/mlb_model/data/foundation/batter_quality_builder.py`
- Create: `C:/Users/johnny/Desktop/mlb_model/tests/test_batter_quality_builder.py`

- [ ] **Step 1: Write failing test (leak guard is critical)**

`tests/test_batter_quality_builder.py`:

```python
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
    for i in range(50):
        rows.append({
            "batter_id": "A",
            "game_date": date(2025, 4, 1) + pd.Timedelta(days=i % 50).to_pytimedelta(),
            "xwoba_mean": 0.400,
            "pa": 1,
            "xwoba_pa": 1,
            "season": 2025,
        })
    return pd.DataFrame(rows)

def test_hybrid_uses_only_pre_date_data():
    h = _synthetic_pa_history()
    out = compute_batter_quality_pointtime(h, snapshot_dates=[date(2024, 3, 1)])
    a = out[out.batter_id == "A"].iloc[0]
    # No prior data → defaults to league avg (100)
    assert a.batter_xwoba == pytest.approx(100.0, abs=1.0)

def test_hybrid_blends_prior_season_with_current_std():
    h = _synthetic_pa_history()
    # As of mid-2025: prior_season=0.350 (200 PA), current_std=0.400 (small sample)
    out = compute_batter_quality_pointtime(h, snapshot_dates=[date(2025, 5, 1)])
    a = out[out.batter_id == "A"].iloc[0]
    # Hybrid: 0.6 * current + 0.4 * prior (regressed). Result should be > 100 (above avg)
    # Raw: 0.6*0.400 + 0.4*0.350 = 0.380 → /0.320 * 100 = 118.75
    # With regression toward 100, value lands somewhere between 100 and 119
    assert a.batter_xwoba > 105
    assert a.batter_xwoba < 120

def test_unknown_batter_returns_no_row():
    h = _synthetic_pa_history()
    out = compute_batter_quality_pointtime(h, snapshot_dates=[date(2025, 5, 1)])
    assert "Z" not in out.batter_id.values

def test_hybrid_xwoba_pure_compute():
    # prior=0.350, current=0.400, current_pa=50, league=0.320
    # Hybrid raw = 0.6*0.400 + 0.4*0.350 = 0.380
    # Regress: weight = 50/(50+200) = 0.20 → regressed = 0.20*0.380 + 0.80*0.320 = 0.332
    # Scale: 0.332/0.320 * 100 = 103.75
    val = _hybrid_xwoba(prior_xwoba=0.350, std_xwoba=0.400, std_pa=50,
                        league_xwoba=0.320, regression_pa=200)
    assert val == pytest.approx(103.75, abs=0.5)
```

- [ ] **Step 2: Run test, confirm fails**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_batter_quality_builder.py -v
```

- [ ] **Step 3: Implement `data/foundation/batter_quality_builder.py`**

```python
"""
data/foundation/batter_quality_builder.py

Point-in-time batter quality table.

For each (batter_id, as_of_date) compute:
    batter_xwoba: hybrid xwOBA scaled to 100-center (higher = better hitter).
                  Hybrid: 0.6 * current_STD + 0.4 * prior_season,
                  regressed to league mean by PA.

CRITICAL: only PAs with game_date < as_of_date may contribute.
"""
from __future__ import annotations
import logging
from datetime import date
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("data/features/batter_quality.parquet")
LEAGUE_AVG_XWOBA = 0.320
REGRESSION_PA = 200
PRIOR_WEIGHT = 0.4


def _hybrid_xwoba(prior_xwoba: float | None, std_xwoba: float | None,
                  std_pa: float, league_xwoba: float = LEAGUE_AVG_XWOBA,
                  regression_pa: float = REGRESSION_PA) -> float:
    """Returns batter_xwoba on 100-center scale."""
    has_prior = prior_xwoba is not None and not pd.isna(prior_xwoba)
    has_std = std_xwoba is not None and not pd.isna(std_xwoba)
    if not has_prior and not has_std:
        return 100.0
    if not has_prior:
        raw = std_xwoba
    elif not has_std:
        raw = prior_xwoba
    else:
        raw = (1.0 - PRIOR_WEIGHT) * std_xwoba + PRIOR_WEIGHT * prior_xwoba
    # Regress to league mean by sample
    weight = std_pa / (std_pa + regression_pa) if std_pa > 0 else 0.0
    regressed = weight * raw + (1.0 - weight) * league_xwoba
    return (regressed / league_xwoba) * 100.0


def compute_batter_quality_pointtime(
    history: pd.DataFrame,
    snapshot_dates: list[date] | None = None,
) -> pd.DataFrame:
    """
    history columns: batter_id, game_date, xwoba_mean, pa, xwoba_pa, season

    snapshot_dates: dates to compute "as of"; defaults to all unique game_dates
    plus a couple of test fixture dates.
    """
    cols = ["batter_id", "as_of_date", "batter_xwoba", "n_pa_std"]
    if history.empty:
        return pd.DataFrame(columns=cols)

    h = history.copy()
    h["game_date"] = pd.to_datetime(h["game_date"]).dt.date
    h["pa"] = h["pa"].astype(int)
    # Weighted xwoba: only batted-ball PAs contributed to xwoba_mean
    h["xwoba_weight"] = h["xwoba_pa"].fillna(0).astype(int)
    h["xwoba_total"] = h["xwoba_mean"].fillna(0) * h["xwoba_weight"]

    if snapshot_dates is None:
        snapshot_dates = sorted(set(h["game_date"].tolist()) |
                                {date(2024, 3, 1), date(2025, 5, 1)})

    batters = h["batter_id"].unique()
    out_rows = []
    for batter_id in batters:
        bh = h[h["batter_id"] == batter_id]
        for as_of in snapshot_dates:
            past = bh[bh["game_date"] < as_of]
            if past.empty:
                # Pre-debut: no row (caller imputes via live lookup)
                continue
            cur_season = as_of.year
            std = past[past["season"] == cur_season]
            prior = past[past["season"] == cur_season - 1]

            std_pa = float(std["pa"].sum()) if not std.empty else 0.0
            std_xpa = float(std["xwoba_weight"].sum()) if not std.empty else 0.0
            std_xwoba = (float(std["xwoba_total"].sum()) / std_xpa) if std_xpa > 0 else None
            prior_xpa = float(prior["xwoba_weight"].sum()) if not prior.empty else 0.0
            prior_xwoba = (float(prior["xwoba_total"].sum()) / prior_xpa) if prior_xpa > 0 else None

            batter_xwoba = _hybrid_xwoba(prior_xwoba, std_xwoba, std_pa)
            out_rows.append({
                "batter_id": batter_id,
                "as_of_date": as_of,
                "batter_xwoba": batter_xwoba,
                "n_pa_std": int(std_pa),
            })

    return pd.DataFrame(out_rows, columns=cols)


def build_from_statcast(seasons: list[int] | None = None) -> pd.DataFrame:
    """End-to-end: aggregate statcast → point-in-time table."""
    from data.foundation.statcast_batter_aggregator import aggregate_from_statcast_dir
    history = aggregate_from_statcast_dir(seasons=seasons)
    history["batter_id"] = history["batter_id"].astype(str)
    return compute_batter_quality_pointtime(history)


def main() -> None:
    seasons = list(range(2018, 2026))
    df = build_from_statcast(seasons)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests (4/4 PASSED)**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_batter_quality_builder.py -v
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/data/foundation/batter_quality_builder.py mlb_model/tests/test_batter_quality_builder.py && git commit -m "mlb_model: add point-in-time batter quality builder (#2)"
```

---

## Task 3: Batter quality live lookup

**Files:**
- Create: `C:/Users/johnny/Desktop/mlb_model/sports/mlb/batter_quality_live.py`
- Create: `C:/Users/johnny/Desktop/mlb_model/tests/test_batter_quality_live.py`

- [ ] **Step 1: Write failing test**

`tests/test_batter_quality_live.py`:

```python
from datetime import date
import pandas as pd
import pytest
from sports.mlb.batter_quality_live import (
    lookup_batter_xwoba, lookup_batters_avg_xwoba, _set_test_table, BatterQuality
)

@pytest.fixture(autouse=True)
def reset():
    yield
    _set_test_table(None)

def _table():
    return pd.DataFrame([
        {"batter_id": "p1", "as_of_date": date(2025, 7, 1), "batter_xwoba": 120.0, "n_pa_std": 250},
        {"batter_id": "p2", "as_of_date": date(2025, 7, 1), "batter_xwoba": 95.0, "n_pa_std": 100},
    ])

def test_lookup_known_batter():
    _set_test_table(_table())
    q = lookup_batter_xwoba("p1", date(2025, 7, 1))
    assert q.batter_xwoba == pytest.approx(120.0)
    assert q.imputed is False

def test_lookup_unknown_batter_imputes_100():
    _set_test_table(pd.DataFrame(columns=["batter_id", "as_of_date", "batter_xwoba", "n_pa_std"]))
    q = lookup_batter_xwoba("rookie", date(2025, 7, 1))
    assert q.batter_xwoba == 100.0
    assert q.imputed is True

def test_lookup_avg_aggregates_known_and_imputes_unknown():
    _set_test_table(_table())
    avg = lookup_batters_avg_xwoba(["p1", "p2", "rookie"], date(2025, 7, 1))
    # 120, 95, 100 → mean = 105
    assert avg == pytest.approx(105.0, abs=0.1)

def test_lookup_avg_empty_list_returns_100():
    _set_test_table(_table())
    assert lookup_batters_avg_xwoba([], date(2025, 7, 1)) == 100.0
```

- [ ] **Step 2: Run test, confirm fails**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_batter_quality_live.py -v
```

- [ ] **Step 3: Implement `sports/mlb/batter_quality_live.py`**

```python
"""
sports/mlb/batter_quality_live.py — Live (batter_id, date) → batter_xwoba.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional, Iterable
import pandas as pd

logger = logging.getLogger(__name__)
_TABLE: Optional[pd.DataFrame] = None
_TABLE_PATH = Path("data/features/batter_quality.parquet")
LEAGUE_MEAN = 100.0


@dataclass
class BatterQuality:
    batter_xwoba: float    # 100-center (>100 above avg)
    n_pa_std: int
    imputed: bool


def _load_table() -> pd.DataFrame:
    global _TABLE
    if _TABLE is None:
        if _TABLE_PATH.exists():
            _TABLE = pd.read_parquet(_TABLE_PATH)
            _TABLE["as_of_date"] = pd.to_datetime(_TABLE["as_of_date"]).dt.date
        else:
            _TABLE = pd.DataFrame(columns=["batter_id", "as_of_date",
                                           "batter_xwoba", "n_pa_std"])
    return _TABLE


def _set_test_table(df: Optional[pd.DataFrame]) -> None:
    global _TABLE
    _TABLE = df


def lookup_batter_xwoba(batter_id: str, as_of: date) -> BatterQuality:
    table = _load_table()
    if table.empty:
        return BatterQuality(LEAGUE_MEAN, 0, imputed=True)
    rows = table[table["batter_id"] == str(batter_id)]
    if rows.empty:
        return BatterQuality(LEAGUE_MEAN, 0, imputed=True)
    exact = rows[rows["as_of_date"] == as_of]
    if not exact.empty:
        r = exact.iloc[0]
    else:
        prior = rows[rows["as_of_date"] <= as_of].sort_values("as_of_date", ascending=False)
        if prior.empty:
            return BatterQuality(LEAGUE_MEAN, 0, imputed=True)
        r = prior.iloc[0]
    return BatterQuality(
        batter_xwoba=float(r["batter_xwoba"]),
        n_pa_std=int(r["n_pa_std"]),
        imputed=False,
    )


def lookup_batters_avg_xwoba(batter_ids: Iterable, as_of: date) -> float:
    """Mean batter_xwoba across the given batter_ids; impute 100 for unknowns."""
    ids = [str(b) for b in batter_ids]
    if not ids:
        return LEAGUE_MEAN
    vals = [lookup_batter_xwoba(b, as_of).batter_xwoba for b in ids]
    return sum(vals) / len(vals)
```

- [ ] **Step 4: Run tests (4/4 PASSED)**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_batter_quality_live.py -v
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/sports/mlb/batter_quality_live.py mlb_model/tests/test_batter_quality_live.py && git commit -m "mlb_model: add batter quality live lookup (#2)"
```

---

## Task 4: Live lineup feed (MLB Stats API)

**Files:**
- Create: `C:/Users/johnny/Desktop/mlb_model/sports/mlb/lineup_live.py`
- Create: `C:/Users/johnny/Desktop/mlb_model/tests/test_lineup_live.py`

- [ ] **Step 1: Write failing test (mocked HTTP)**

`tests/test_lineup_live.py`:

```python
import pytest
from sports.mlb.lineup_live import (
    fetch_live_lineup, parse_live_response, LineupSnapshot, LineupError,
)

_MOCK_LIVE = {
    "gameData": {
        "teams": {
            "home": {"abbreviation": "LAA"},
            "away": {"abbreviation": "SDP"},
        },
    },
    "liveData": {
        "linescore": {
            "offense": {"batter": {"id": 600001}, "battingOrder": "5"},
            "defense": {"pitcher": {"id": 700001}},
        },
        "boxscore": {
            "teams": {
                "home": {
                    "battingOrder": [600100, 600101, 600102, 600103, 600104,
                                     600001, 600106, 600107, 600108],
                    "players": {
                        "ID600001": {"person": {"id": 600001}, "stats": {}, "batSide": {"code": "L"}},
                    },
                },
                "away": {
                    "battingOrder": [600200, 600201, 600202, 600203, 600204,
                                     600205, 600206, 600207, 600208],
                    "players": {
                        "ID700001": {"person": {"id": 700001}, "pitchHand": {"code": "R"}},
                    },
                },
            },
        },
    },
}

def test_parse_extracts_current_batter_and_lineups():
    snap = parse_live_response(_MOCK_LIVE)
    assert isinstance(snap, LineupSnapshot)
    assert snap.current_batter_id == 600001
    assert snap.current_pitcher_id == 700001
    assert snap.current_batter_stand == "L"
    assert snap.current_pitcher_throws == "R"
    assert snap.current_lineup_position == 6   # 0-indexed 5 → 1-indexed 6
    assert snap.home_lineup == [600100, 600101, 600102, 600103, 600104,
                                 600001, 600106, 600107, 600108]

def test_parse_returns_none_on_missing_fields():
    bad = {"gameData": {}, "liveData": {}}
    assert parse_live_response(bad) is None

def test_fetch_raises_on_http_error(monkeypatch):
    def boom(*a, **kw):
        raise OSError("network down")
    monkeypatch.setattr("sports.mlb.lineup_live._http_get_json", boom)
    with pytest.raises(LineupError):
        fetch_live_lineup(game_pk=999)

def test_fetch_returns_parsed(monkeypatch):
    monkeypatch.setattr("sports.mlb.lineup_live._http_get_json", lambda url: _MOCK_LIVE)
    snap = fetch_live_lineup(game_pk=999)
    assert snap.current_batter_id == 600001
```

- [ ] **Step 2: Run test, confirm fails**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_lineup_live.py -v
```

- [ ] **Step 3: Implement `sports/mlb/lineup_live.py`**

```python
"""
sports/mlb/lineup_live.py — Live lineup + current batter/pitcher fetch from MLB Stats API.

Endpoint: https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live
"""
from __future__ import annotations
import json
import logging
import urllib.request
from dataclasses import dataclass, field
from typing import Optional
import time

logger = logging.getLogger(__name__)

MLB_LIVE_FEED = "https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
_CACHE: dict[int, tuple[float, "LineupSnapshot"]] = {}
_CACHE_TTL_SEC = 15.0


class LineupError(Exception):
    pass


@dataclass
class LineupSnapshot:
    current_batter_id: int
    current_pitcher_id: int
    current_batter_stand: str    # L / R / S
    current_pitcher_throws: str  # L / R
    current_lineup_position: int # 1-9
    home_lineup: list[int] = field(default_factory=list)
    away_lineup: list[int] = field(default_factory=list)


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "mlb_model/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def parse_live_response(data: dict) -> Optional[LineupSnapshot]:
    """Extract the fields we need from the MLB Stats API live feed response."""
    try:
        live = data.get("liveData", {})
        ls = live.get("linescore", {})
        bs = live.get("boxscore", {})
        offense = ls.get("offense") or {}
        defense = ls.get("defense") or {}
        cur_batter = (offense.get("batter") or {}).get("id")
        cur_pitcher = (defense.get("pitcher") or {}).get("id")
        if cur_batter is None or cur_pitcher is None:
            return None

        # batting order is 0-indexed string in some responses; coerce to int + 1
        order_str = offense.get("battingOrder")
        if order_str is None:
            return None
        cur_pos = int(order_str) + 1   # 5 → 6 (1-indexed)

        teams = bs.get("teams") or {}
        home_lineup = list(teams.get("home", {}).get("battingOrder") or [])
        away_lineup = list(teams.get("away", {}).get("battingOrder") or [])

        # batter handedness from boxscore
        home_players = teams.get("home", {}).get("players") or {}
        away_players = teams.get("away", {}).get("players") or {}
        all_players = {**home_players, **away_players}
        batter_player = all_players.get(f"ID{cur_batter}", {})
        pitcher_player = all_players.get(f"ID{cur_pitcher}", {})
        batter_stand = (batter_player.get("batSide") or {}).get("code", "?")
        pitcher_throws = (pitcher_player.get("pitchHand") or {}).get("code", "?")

        return LineupSnapshot(
            current_batter_id=int(cur_batter),
            current_pitcher_id=int(cur_pitcher),
            current_batter_stand=batter_stand,
            current_pitcher_throws=pitcher_throws,
            current_lineup_position=cur_pos,
            home_lineup=[int(x) for x in home_lineup],
            away_lineup=[int(x) for x in away_lineup],
        )
    except Exception as e:
        logger.warning("parse_live_response failed: %s", e)
        return None


def fetch_live_lineup(game_pk: int) -> LineupSnapshot:
    """Fetch + cache (15s TTL). Raises LineupError on network failure."""
    now = time.monotonic()
    cached = _CACHE.get(game_pk)
    if cached is not None and (now - cached[0]) < _CACHE_TTL_SEC:
        return cached[1]
    url = MLB_LIVE_FEED.format(game_pk=game_pk)
    try:
        data = _http_get_json(url)
    except Exception as e:
        raise LineupError(f"MLB Stats API fetch failed: {e}") from e
    snap = parse_live_response(data)
    if snap is None:
        raise LineupError(f"could not parse lineup for game_pk={game_pk}")
    _CACHE[game_pk] = (now, snap)
    return snap
```

- [ ] **Step 4: Run tests (4/4 PASSED)**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_lineup_live.py -v
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/sports/mlb/lineup_live.py mlb_model/tests/test_lineup_live.py && git commit -m "mlb_model: add MLB Stats API lineup_live (current batter + lineups) (#2)"
```

---

## Task 5: Snapshot builder — 7 new columns

**Files:**
- Modify: `C:/Users/johnny/Desktop/mlb_model/data/state_snapshot_builder.py`

This is the largest snapshot builder change yet. The builder iterates pitches per game; we need to capture batter and lineup info from the pitch stream.

- [ ] **Step 1: Read the current snapshot dict literal location**

```bash
cd C:/Users/johnny/Desktop/mlb_model && grep -n "home_pitcher_id\|park_id\|pregame_prior_source" data/state_snapshot_builder.py
```

The snapshot dict literal is around line 253. We added `park_id` and `pregame_prior_source` in #1.5. Now extend it further.

- [ ] **Step 2: Read the pitch-iteration block to understand context**

```bash
cd C:/Users/johnny/Desktop/mlb_model && sed -n '155,260p' data/state_snapshot_builder.py
```

You should see a loop iterating pitch rows. The `pa_row` variable has a `batter` field, `stand` field, etc. (Statcast columns). The `pitcher_entry_ab` dict tracks pitcher entry. We need a similar structure to track lineup.

- [ ] **Step 3: Build per-game lineup before the PA loop**

Find the function that processes one game (likely `build_snapshots_for_season` or similar). Right BEFORE the main per-PA loop in that function, add:

```python
        # ── Phase-2: derive per-game lineups + per-PA batter info ────────────
        # Lineups: first-9-unique batters per side from the game's PAs
        home_pa_batters = []
        away_pa_batters = []
        seen_home = set()
        seen_away = set()
        for _, _row in game_df.iterrows():
            _bat = int(_row["batter"]) if not pd.isna(_row.get("batter")) else None
            _half = _row.get("inning_topbot")  # 'Top' or 'Bot'
            if _bat is None:
                continue
            # In top-of-inning, away team bats; in bottom, home bats
            if _half == "Top" and _bat not in seen_away:
                seen_away.add(_bat); away_pa_batters.append(_bat)
            elif _half == "Bot" and _bat not in seen_home:
                seen_home.add(_bat); home_pa_batters.append(_bat)
        home_lineup_ids = home_pa_batters[:9]
        away_lineup_ids = away_pa_batters[:9]
```

Then in the per-PA snapshot loop, use:
- `pa_row["batter"]` → `batter_id`
- `pa_row["stand"]` → `batter_stand`
- `pa_row["p_throws"]` → either home or away pitcher's p_throws depending on inning_half

- [ ] **Step 4: Add the 7 new fields to the snapshot dict literal**

Find the existing snapshot dict literal (where `"park_id": lookup_park_id(home_team)` lives). Insert these 7 NEW key-value pairs IMMEDIATELY after the `"pregame_prior_source": 1,` line:

```python
                "batter_id": int(pa_row["batter"]) if not pd.isna(pa_row.get("batter")) else -1,
                "batter_stand": str(pa_row.get("stand", "?")),
                "home_pitcher_p_throws": str(pa_row.get("p_throws", "?")) if pa_row.get("inning_topbot") == "Top" else "?",
                "away_pitcher_p_throws": str(pa_row.get("p_throws", "?")) if pa_row.get("inning_topbot") == "Bot" else "?",
                "home_lineup_ids": home_lineup_ids,
                "away_lineup_ids": away_lineup_ids,
                "current_lineup_position": (
                    (home_lineup_ids.index(int(pa_row["batter"])) + 1)
                    if pa_row.get("inning_topbot") == "Bot" and int(pa_row["batter"]) in home_lineup_ids
                    else (away_lineup_ids.index(int(pa_row["batter"])) + 1)
                    if pa_row.get("inning_topbot") == "Top" and int(pa_row["batter"]) in away_lineup_ids
                    else 0
                ),
```

(Indentation must match the surrounding 16 spaces.)

NOTE: `home_pitcher_p_throws` only fills when away is batting (top of inning, home pitcher on mound). Otherwise we mark "?" for that side. This is fine — it just means each row only has one valid p_throws and the consumer needs to pick the right one based on `inning_half`. Simpler: store BOTH as best-known values that get refreshed each row.

Actually a cleaner approach: track running `home_pitcher_throws` and `away_pitcher_throws` variables across the PA loop (similar to existing `home_pitcher_id` / `away_pitcher_id`), and use those in the dict. Add:

```python
        home_pitcher_throws_running = "?"
        away_pitcher_throws_running = "?"
```

near where `home_starter_id`/`away_starter_id` are initialized. Then in the per-pitch loop where pitcher_id is set, also update:

```python
            _pthrows = str(pitch_row.get("p_throws", "?")) if not pd.isna(pitch_row.get("p_throws")) else "?"
            if half == 0 and pitcher_id != away_starter_id:
                # top of inning: away batting, home pitcher
                # actually: top of inning means away team is batting → home is pitching
                home_pitcher_throws_running = _pthrows
            elif half == 1:
                away_pitcher_throws_running = _pthrows
```

Then the dict uses the running variables instead of conditionals. Adjust based on the actual variable names you see in the file.

- [ ] **Step 5: Smoke test the import**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -c "
import data.state_snapshot_builder
print('import OK')
"
```

- [ ] **Step 6: Verify with one season**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m data.state_snapshot_builder --seasons 2025 && python -c "
import pandas as pd
df = pd.read_parquet('data/features/snapshots_2025.parquet')
print('cols:', list(df.columns))
new_cols = ['batter_id', 'batter_stand', 'home_pitcher_p_throws',
            'away_pitcher_p_throws', 'home_lineup_ids', 'away_lineup_ids',
            'current_lineup_position']
for c in new_cols:
    assert c in df.columns, f'missing {c}'
print('all 7 new columns present')
print('batter_id non-default rate:', (df.batter_id != -1).mean())
print('lineup avg length:', df.home_lineup_ids.apply(len).mean())
"
```
Expected: 7 new cols present, batter_id rate ≈ 1.0, lineup avg length ≈ 9.

- [ ] **Step 7: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/data/state_snapshot_builder.py && git commit -m "mlb_model: emit batter_id + lineups + p_throws on snapshot rows (#2)"
```

---

## Task 6: Feature store enrichment — 5 new features

**Files:**
- Modify: `C:/Users/johnny/Desktop/mlb_model/data/feature_store.py`

- [ ] **Step 1: Extend `FEATURE_COLUMNS` from 30 → 35**

Find the existing `FEATURE_COLUMNS = [...]` block. Append 5 new entries after the existing `"pregame_prior_source"` entry (the last from #1):

```python
    # ── PHASE-2 enrichment (added 2026-04-19) ────────────────────────────────
    "current_batter_xwoba",
    "next3_avg_xwoba",
    "lineup_avg_xwoba",
    "current_batter_platoon_advantage",
    "current_batter_xwoba_x_late",
```

- [ ] **Step 2: Extend `enrich_with_phase1_features` to also handle phase-2**

Find the existing `def enrich_with_phase1_features(features: pd.DataFrame) -> pd.DataFrame:` function. After the existing logic but BEFORE the `return out` line, append:

```python
    # ── Phase-2: batter quality enrichment ───────────────────────────────────
    bq_path = FEATURE_DIR / "batter_quality.parquet"
    can_join_batter = (
        bq_path.exists()
        and "batter_id" in out.columns
        and "date" in out.columns
        and "home_lineup_ids" in out.columns
        and "away_lineup_ids" in out.columns
        and "current_lineup_position" in out.columns
        and "batter_stand" in out.columns
    )

    if can_join_batter:
        bq = pd.read_parquet(bq_path)
        bq["as_of_date"] = pd.to_datetime(bq["as_of_date"]).dt.date
        bq["batter_id"] = bq["batter_id"].astype(str)

        # Build a (str_id, date) → batter_xwoba dict for fast lookup
        bq_lookup = dict(
            zip(zip(bq["batter_id"], bq["as_of_date"]), bq["batter_xwoba"])
        )

        def _xwoba_for(bid, d):
            return bq_lookup.get((str(bid), d), 100.0)

        # Current batter
        join_dates = pd.to_datetime(out["date"]).dt.date
        out["current_batter_xwoba"] = [
            _xwoba_for(b, d) for b, d in zip(out["batter_id"], join_dates)
        ]

        # Next-3 average: depends on which side is batting
        # (top → away batting, bot → home batting)
        def _next3(row, d):
            half = row["half"]
            pos = int(row["current_lineup_position"])
            lineup = row["away_lineup_ids"] if half == 0 else row["home_lineup_ids"]
            if not lineup or pos < 1:
                return 100.0
            # next 3 spots after current (wrapping around 1..9)
            ids = []
            for i in range(1, 4):
                idx = (pos - 1 + i) % len(lineup)
                ids.append(lineup[idx])
            if not ids:
                return 100.0
            return sum(_xwoba_for(b, d) for b in ids) / len(ids)

        out["next3_avg_xwoba"] = [
            _next3(row, d) for (_, row), d in zip(out.iterrows(), join_dates)
        ]

        # Lineup avg: full 9 batters of the batting side
        def _lineup_avg(row, d):
            half = row["half"]
            lineup = row["away_lineup_ids"] if half == 0 else row["home_lineup_ids"]
            if not lineup:
                return 100.0
            return sum(_xwoba_for(b, d) for b in lineup) / len(lineup)

        out["lineup_avg_xwoba"] = [
            _lineup_avg(row, d) for (_, row), d in zip(out.iterrows(), join_dates)
        ]
    else:
        logger.warning("phase-2 enrichment: required columns missing; using neutral defaults")
        out["current_batter_xwoba"] = 100.0
        out["next3_avg_xwoba"] = 100.0
        out["lineup_avg_xwoba"] = 100.0

    # Platoon advantage flag (no parquet needed, derived from row)
    if "batter_stand" in out.columns and "home_pitcher_p_throws" in out.columns and "away_pitcher_p_throws" in out.columns:
        def _platoon(row):
            stand = row["batter_stand"]
            half = row["half"]
            # In top of inning, away bats vs home pitcher; in bot, home vs away
            p_throws = row["home_pitcher_p_throws"] if half == 0 else row["away_pitcher_p_throws"]
            if stand == "S":   # switch hitters always have advantage
                return 1.0
            if (stand == "L" and p_throws == "R") or (stand == "R" and p_throws == "L"):
                return 1.0
            return 0.0
        out["current_batter_platoon_advantage"] = out.apply(_platoon, axis=1).astype(float)
    else:
        out["current_batter_platoon_advantage"] = 0.0

    out["current_batter_xwoba_x_late"] = (out["current_batter_xwoba"] - 100.0) * out["late_game"]
```

- [ ] **Step 3: Update the NaN guard for the new columns**

Find the existing NaN guard block. Update the `phase_one_cols` exclusion list to also exclude phase-2 columns:

```python
    base_cols = [c for c in FEATURE_COLUMNS if c not in (
        "home_sp_quality", "away_sp_quality",
        "home_sp_recent_form", "away_sp_recent_form",
        "sp_quality_diff", "park_run_factor",
        "park_run_factor_x_late", "pregame_prior_source",
        # phase-2:
        "current_batter_xwoba", "next3_avg_xwoba", "lineup_avg_xwoba",
        "current_batter_platoon_advantage", "current_batter_xwoba_x_late",
    )]
```

- [ ] **Step 4: Smoke test**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -c "
from data.feature_store import FEATURE_COLUMNS, enrich_with_phase1_features
import pandas as pd
print('feature count:', len(FEATURE_COLUMNS))
assert len(FEATURE_COLUMNS) == 35
synthetic = pd.DataFrame({'pregame_logit': [0.0], 'score_diff': [0], 'late_game': [0.5], 'half': [0]})
out = enrich_with_phase1_features(synthetic)
for col in ['current_batter_xwoba', 'next3_avg_xwoba', 'lineup_avg_xwoba',
            'current_batter_platoon_advantage', 'current_batter_xwoba_x_late']:
    assert col in out.columns, f'missing {col}'
print('all 5 phase-2 columns present in synthetic enrich')
"
```
Expected: feature count: 35, all 5 phase-2 columns present.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/data/feature_store.py && git commit -m "mlb_model: extend feature_store with 5 phase-2 batter columns (#2)"
```

---

## Task 7: Inference path — 35-col vector

**Files:**
- Modify: `C:/Users/johnny/Desktop/mlb_model/sports/mlb/winprob_inference.py`
- Modify: `C:/Users/johnny/Desktop/mlb_model/tests/test_winprob_inference.py`

- [ ] **Step 1: Add `_PHASE2_FEATURE_NAMES` constant**

After the existing `_PHASE1_FEATURE_NAMES` tuple, INSERT:

```python
_PHASE2_FEATURE_NAMES = (
    "current_batter_xwoba", "next3_avg_xwoba", "lineup_avg_xwoba",
    "current_batter_platoon_advantage", "current_batter_xwoba_x_late",
)
```

- [ ] **Step 2: Modify `_build_feature_vector` to accept `phase2_extras`**

Change signature:

```python
def _build_feature_vector(
    snapshot,
    pregame_win_prob: float,
    phase1_extras: dict | None = None,
    phase2_extras: dict | None = None,
) -> tuple[np.ndarray, dict[str, float], float]:
```

After the existing phase-1 feature block, BEFORE the `quality = 1.0` line, INSERT:

```python
    # Phase-2 batter features
    p2 = phase2_extras or {}
    feat["current_batter_xwoba"] = float(p2.get("current_batter_xwoba", 100.0))
    feat["next3_avg_xwoba"] = float(p2.get("next3_avg_xwoba", 100.0))
    feat["lineup_avg_xwoba"] = float(p2.get("lineup_avg_xwoba", 100.0))
    feat["current_batter_platoon_advantage"] = float(p2.get("current_batter_platoon_advantage", 0.0))
    feat["current_batter_xwoba_x_late"] = (feat["current_batter_xwoba"] - 100.0) * feat["late_game"]
```

In the data_quality block, ADD a penalty for batter imputation:

```python
    if p2.get("current_batter_imputed"):
        quality -= 0.03
```

- [ ] **Step 3: Modify `infer` to pass through `phase2_extras`**

```python
def infer(snapshot, pregame_win_prob: float = 0.54,
          phase1_extras: dict | None = None,
          phase2_extras: dict | None = None) -> InferenceResult:
    if _model is None or _calibrator is None:
        raise RuntimeError("Model artifacts not loaded.")
    X, feat_dict, quality = _build_feature_vector(snapshot, pregame_win_prob, phase1_extras, phase2_extras)
    if hasattr(_model, "predict_proba"):
        raw_prob = float(_model.predict_proba(X)[0, 1])
    else:
        raw_prob = float(_model.predict(X)[0])
    cal_prob = float(_calibrator.predict(np.array([raw_prob])))
    cal_prob = max(0.01, min(0.99, cal_prob))
    return InferenceResult(
        p_home=round(cal_prob, 6), p_away=round(1.0 - cal_prob, 6),
        raw_prob=round(raw_prob, 6), features=feat_dict,
        model_version=_manifest.get("model_version", "mlb_winprob_v1"),
        data_quality=round(quality, 4),
    )


def infer_for_team(snapshot, tracked_team, pregame_win_prob_home: float = 0.54,
                   phase1_extras: dict | None = None,
                   phase2_extras: dict | None = None):
    from sports.mlb.team_normalizer import normalize
    result = infer(snapshot, pregame_win_prob_home, phase1_extras, phase2_extras)
    tracked = normalize(tracked_team)
    p_tracked = result.p_home if tracked == snapshot.home_team else result.p_away
    return round(p_tracked, 6), result
```

- [ ] **Step 4: Add tests**

Append to `tests/test_winprob_inference.py`:

```python
def test_phase2_feature_names_count():
    from sports.mlb.winprob_inference import _PHASE2_FEATURE_NAMES
    assert len(_PHASE2_FEATURE_NAMES) == 5


def test_build_vector_with_phase2_extras():
    from sports.mlb import winprob_inference as wi
    wi._feature_columns = [
        "pregame_logit","score_diff","abs_score_diff","tied","inning","half","outs",
        "game_progress","late_game","base_state","base_state_value",
        "score_diff_x_late","base_value_x_late","tied_x_late",
        "home_pitch_count_norm","home_tto","home_is_bullpen",
        "away_pitch_count_norm","away_tto","away_is_bullpen",
        "elo_diff_norm","late_tie_bottom",
        "home_sp_quality","away_sp_quality","home_sp_recent_form","away_sp_recent_form",
        "sp_quality_diff","park_run_factor","park_run_factor_x_late","pregame_prior_source",
        "current_batter_xwoba","next3_avg_xwoba","lineup_avg_xwoba",
        "current_batter_platoon_advantage","current_batter_xwoba_x_late",
    ]
    snap = SimpleNamespace(
        score_diff=0, inning=5, inning_half=0, outs=1, outs_elapsed=24,
        base_state=0, home_pitch_count=70, away_pitch_count=72,
        home_tto=2.0, away_tto=2.0, home_is_bullpen=False, away_is_bullpen=False,
    )
    p1 = {"home_sp_quality": 100, "away_sp_quality": 100,
          "home_sp_recent_form": 0, "away_sp_recent_form": 0,
          "park_run_factor": 1.0, "pregame_prior_source": 0,
          "home_sp_imputed": False, "away_sp_imputed": False}
    p2 = {"current_batter_xwoba": 120, "next3_avg_xwoba": 105,
          "lineup_avg_xwoba": 100, "current_batter_platoon_advantage": 1,
          "current_batter_imputed": False}
    X, feat, q = wi._build_feature_vector(snap, 0.55, p1, p2)
    assert X.shape == (1, 35)
    assert feat["current_batter_xwoba"] == 120
    assert feat["current_batter_platoon_advantage"] == 1.0
    # x_late = (120 - 100) * late_game; late_game = (24/54)**1.5
    expected_late_game = (24/54) ** 1.5
    assert feat["current_batter_xwoba_x_late"] == pytest.approx(20 * expected_late_game)
```

(NOTE: ensure `import pytest` and `from types import SimpleNamespace` are present at the top of the test file.)

- [ ] **Step 5: Run tests (5/5 PASSED — 3 existing + 2 new)**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_winprob_inference.py -v
```

- [ ] **Step 6: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/sports/mlb/winprob_inference.py mlb_model/tests/test_winprob_inference.py && git commit -m "mlb_model: extend inference vector to 35 cols (phase-2) (#2)"
```

---

## Task 8: Wire phase-2 into recommendation_api

**Files:**
- Modify: `C:/Users/johnny/Desktop/mlb_model/integration/recommendation_api.py`

- [ ] **Step 1: Add new imports inside `generate_recommendation_for_game`**

Find the imports block at the top of the function. Append:

```python
    from sports.mlb.batter_quality_live import lookup_batter_xwoba, lookup_batters_avg_xwoba
    from sports.mlb.lineup_live import fetch_live_lineup, LineupError
```

- [ ] **Step 2: Build phase2_extras after the existing phase1_extras block**

Find where `phase1_extras` is built. RIGHT AFTER its closing `}`, INSERT:

```python
    # Phase-2: batter quality + lineup
    p2_imputed = False
    try:
        # snap.game_pk should exist; fall back to int conversion of game_id if needed
        gpk = int(getattr(snap, "game_pk", None) or getattr(snap, "game_id", 0))
        lineup_snap = fetch_live_lineup(gpk) if gpk else None
    except (LineupError, Exception) as _e:
        logger.warning("lineup fetch failed: %s", _e)
        lineup_snap = None

    if lineup_snap is not None:
        cur_batter = lookup_batter_xwoba(str(lineup_snap.current_batter_id), _gd)
        # next-3 IDs based on lineup position + inning_half
        if snap.inning_half == 0:   # top → away batting
            lineup_ids = lineup_snap.away_lineup
        else:
            lineup_ids = lineup_snap.home_lineup
        pos = lineup_snap.current_lineup_position
        next3_ids = []
        if lineup_ids and pos > 0:
            for i in range(1, 4):
                idx = (pos - 1 + i) % len(lineup_ids)
                next3_ids.append(lineup_ids[idx])
        next3_avg = lookup_batters_avg_xwoba(next3_ids, _gd) if next3_ids else 100.0
        lineup_avg = lookup_batters_avg_xwoba(lineup_ids, _gd) if lineup_ids else 100.0
        # platoon
        stand = lineup_snap.current_batter_stand
        throws = lineup_snap.current_pitcher_throws
        if stand == "S":
            platoon = 1.0
        elif (stand == "L" and throws == "R") or (stand == "R" and throws == "L"):
            platoon = 1.0
        else:
            platoon = 0.0
        p2_imputed = cur_batter.imputed
        phase2_extras = {
            "current_batter_xwoba": cur_batter.batter_xwoba,
            "next3_avg_xwoba": next3_avg,
            "lineup_avg_xwoba": lineup_avg,
            "current_batter_platoon_advantage": platoon,
            "current_batter_imputed": p2_imputed,
        }
    else:
        phase2_extras = {
            "current_batter_xwoba": 100.0, "next3_avg_xwoba": 100.0,
            "lineup_avg_xwoba": 100.0, "current_batter_platoon_advantage": 0.0,
            "current_batter_imputed": True,
        }
        p2_imputed = True
```

- [ ] **Step 3: Update inference call to pass phase2_extras**

Find:

```python
        p_tracked, infer_result = infer_for_team(snap, tracked_team, pregame_prob, phase1_extras)
```

Replace with:

```python
        p_tracked, infer_result = infer_for_team(snap, tracked_team, pregame_prob, phase1_extras, phase2_extras)
```

- [ ] **Step 4: Surface phase-2 in reasons**

Find the existing `# Phase-1 enrichment in reasons` block. APPEND after it (before `if gate_reasons:`):

```python
    # Phase-2 batter features in reasons
    bxw = feat.get("current_batter_xwoba", 100)
    n3 = feat.get("next3_avg_xwoba", 100)
    plat = "+" if feat.get("current_batter_platoon_advantage", 0) else "-"
    reasons.append(
        f"batter: xwoba={bxw:.0f} next3={n3:.0f} platoon{plat}"
    )
    if p2_imputed:
        reasons.append("batter_imputed")
```

- [ ] **Step 5: Syntax + import smoke**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -c "
import py_compile; py_compile.compile('integration/recommendation_api.py', doraise=True)
import integration.recommendation_api
print('imports OK')
"
```

- [ ] **Step 6: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/integration/recommendation_api.py && git commit -m "mlb_model: wire phase-2 batter features into live recommendations (#2)"
```

---

## Task 9: Selfcheck feature count

**Files:**
- Modify: `C:/Users/johnny/Desktop/mlb_model/core/selfcheck.py`

- [ ] **Step 1: Bump `EXPECTED_FEATURE_COUNT`**

Find the line:

```python
EXPECTED_FEATURE_COUNT = 30
```

Change to:

```python
EXPECTED_FEATURE_COUNT = 35
```

- [ ] **Step 2: Smoke test**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -c "
from core.selfcheck import EXPECTED_FEATURE_COUNT
assert EXPECTED_FEATURE_COUNT == 35
print('OK')
"
```

- [ ] **Step 3: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/core/selfcheck.py && git commit -m "mlb_model: bump EXPECTED_FEATURE_COUNT to 35 (#2)"
```

---

## Task 10: Audit framework — phase-2 features list

**Files:**
- Modify: `C:/Users/johnny/Desktop/mlb_model/models/audit_features.py`

- [ ] **Step 1: Add PHASE2_NEW_FEATURES**

After the existing `PHASE1_NEW_FEATURES = [...]` block, INSERT:

```python
PHASE2_NEW_FEATURES = [
    "current_batter_xwoba",
    "next3_avg_xwoba",
    "lineup_avg_xwoba",
    "current_batter_platoon_advantage",
    "current_batter_xwoba_x_late",
]
```

- [ ] **Step 2: Smoke test**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -c "
from models.audit_features import PHASE1_NEW_FEATURES, PHASE2_NEW_FEATURES
print('p1:', len(PHASE1_NEW_FEATURES), 'p2:', len(PHASE2_NEW_FEATURES))
assert len(PHASE2_NEW_FEATURES) == 5
"
```

- [ ] **Step 3: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/models/audit_features.py && git commit -m "mlb_model: add PHASE2_NEW_FEATURES constant for audit (#2)"
```

---

## Task 11: Daily refresh script + cron wrapper

**Files:**
- Create: `C:/Users/johnny/Desktop/mlb_model/scripts/refresh_batter_quality_daily.py`
- Create: `C:/Users/johnny/Desktop/mlb_model/scripts/cron/run_refresh_batter_quality_daily.bat`
- Modify: `C:/Users/johnny/Desktop/mlb_model/scripts/cron/install_scheduled_tasks.bat`

- [ ] **Step 1: Implement `refresh_batter_quality_daily.py`**

```python
"""
scripts/refresh_batter_quality_daily.py — Incremental daily refresh of batter_quality.parquet.
Mirrors scripts/refresh_pitcher_quality_daily.py but for batters.
"""
from __future__ import annotations
import logging
import os
from datetime import date, timedelta
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

BATTER_QUALITY_PATH = Path("data/features/batter_quality.parquet")
STATCAST_DIR = Path("data/raw/statcast")


def _load_yesterdays_pitches(target_date: date) -> pd.DataFrame:
    import pyarrow.parquet as pq
    target_file = STATCAST_DIR / f"{target_date.year}_{target_date.month:02d}.parquet"
    if not target_file.exists():
        return pd.DataFrame()
    try:
        schema_cols = pq.read_schema(target_file).names
    except Exception:
        return pd.DataFrame()
    if "batter" not in schema_cols:
        return pd.DataFrame()
    df = pd.read_parquet(target_file, columns=["batter", "game_date", "events",
                                               "estimated_woba_using_speedangle"])
    if df.empty:
        return pd.DataFrame()
    df["game_date"] = pd.to_datetime(df["game_date"]).dt.date
    return df[df["game_date"] == target_date]


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    yesterday = date.today() - timedelta(days=1)

    pitches = _load_yesterdays_pitches(yesterday)
    if pitches.empty:
        print(f"No Statcast pitches for {yesterday}; nothing to refresh.")
        return 0

    from data.foundation.statcast_batter_aggregator import aggregate_per_batter_per_date
    from data.foundation.batter_quality_builder import compute_batter_quality_pointtime

    new_history = aggregate_per_batter_per_date(pitches)
    if new_history.empty:
        print(f"No qualifying PAs on {yesterday}.")
        return 0
    new_history["batter_id"] = new_history["batter_id"].astype(str)

    if BATTER_QUALITY_PATH.exists():
        existing = pd.read_parquet(BATTER_QUALITY_PATH)
    else:
        existing = pd.DataFrame()

    yesterday_bq = compute_batter_quality_pointtime(
        new_history, snapshot_dates=[yesterday + timedelta(days=1)],
    )
    if existing.empty:
        out = yesterday_bq
    else:
        out = pd.concat([existing, yesterday_bq], ignore_index=True)
        out = out.drop_duplicates(subset=["batter_id", "as_of_date"], keep="last")

    BATTER_QUALITY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = BATTER_QUALITY_PATH.with_suffix(".parquet.tmp")
    out.to_parquet(tmp, index=False)
    os.replace(tmp, BATTER_QUALITY_PATH)
    print(f"Refreshed batter_quality.parquet: +{len(yesterday_bq)} rows for {yesterday}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Implement `scripts/cron/run_refresh_batter_quality_daily.bat`**

```bat
@echo off
REM Daily batter quality refresh — registered as Windows scheduled task `mlb-batter-quality-daily`
cd /d "C:\Users\johnny\Desktop\mlb_model"
"C:\Users\johnny\AppData\Local\Python\pythoncore-3.14-64\python.exe" scripts\refresh_batter_quality_daily.py >> logs\cron.log 2>&1
exit /b %ERRORLEVEL%
```

- [ ] **Step 3: Update `install_scheduled_tasks.bat`**

INSERT after the pitcher-quality block, BEFORE the sharp-odds block:

```bat
echo Installing mlb-batter-quality-daily (08:30 daily)...
schtasks /Create /SC DAILY /TN mlb-batter-quality-daily /TR "C:\Users\johnny\Desktop\mlb_model\scripts\cron\run_refresh_batter_quality_daily.bat" /ST 08:30 /F
if errorlevel 1 goto :err
```

- [ ] **Step 4: Smoke test the script imports**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -c "import py_compile; py_compile.compile('scripts/refresh_batter_quality_daily.py', doraise=True); print('OK')"
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/scripts/refresh_batter_quality_daily.py mlb_model/scripts/cron/run_refresh_batter_quality_daily.bat mlb_model/scripts/cron/install_scheduled_tasks.bat && git commit -m "mlb_model: add daily batter quality refresh + cron wrapper (#2)"
```

---

## Task 12: Integration test extension

**Files:**
- Modify: `C:/Users/johnny/Desktop/mlb_model/tests/integration/test_full_pipeline.py`

- [ ] **Step 1: Append a new integration test**

```python
def test_batter_aggregator_path(tmp_path, monkeypatch):
    """End-to-end: Statcast pitches -> batter aggregator -> batter quality table."""
    monkeypatch.chdir(tmp_path)
    Path("data/features").mkdir(parents=True, exist_ok=True)

    from data.foundation.statcast_batter_aggregator import aggregate_per_batter_per_date
    from data.foundation.batter_quality_builder import compute_batter_quality_pointtime

    rows = []
    # Single batter, 100 PAs in 2024 with xwoba=0.380 (above avg)
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
```

- [ ] **Step 2: Run integration tests (4 PASSED — 3 existing + 1 new)**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/integration/ -v
```

- [ ] **Step 3: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/tests/integration/test_full_pipeline.py && git commit -m "mlb_model: extend integration tests with batter aggregator path (#2)"
```

---

## Task 13: Final smoke + verification

**Files:** none

- [ ] **Step 1: Run full test suite (40+ tests expected)**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/ -v
```
Expected: All tests pass (35 from #1+#1.5 + 5 new units + 1 new integration ≈ 41).

- [ ] **Step 2: Verify all phase-2 module imports**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -c "
import integration.recommendation_api
from data.foundation.statcast_batter_aggregator import aggregate_per_batter_per_date
from data.foundation.batter_quality_builder import build_from_statcast, compute_batter_quality_pointtime
from sports.mlb.batter_quality_live import lookup_batter_xwoba, lookup_batters_avg_xwoba, BatterQuality
from sports.mlb.lineup_live import fetch_live_lineup, parse_live_response, LineupSnapshot
from data.feature_store import FEATURE_COLUMNS
from sports.mlb.winprob_inference import _PHASE2_FEATURE_NAMES
from models.audit_features import PHASE1_NEW_FEATURES, PHASE2_NEW_FEATURES
from core.selfcheck import EXPECTED_FEATURE_COUNT

print('imports OK')
print('FEATURE_COLUMNS:', len(FEATURE_COLUMNS))
print('PHASE1:', len(PHASE1_NEW_FEATURES), '+ PHASE2:', len(PHASE2_NEW_FEATURES))
print('EXPECTED:', EXPECTED_FEATURE_COUNT)
assert len(FEATURE_COLUMNS) == 35
assert EXPECTED_FEATURE_COUNT == 35
print('all consistent: 22 + 8 + 5 = 35')
"
```

- [ ] **Step 3: Document manual operator follow-up**

Print:

> **Operator next steps:**
> 1. Install the new cron task: re-run `scripts\cron\install_scheduled_tasks.bat` (now adds the 4th task)
> 2. Bootstrap batter quality: `python -m data.foundation.batter_quality_builder` (~10 min, local statcast)
> 3. Regenerate snapshots with phase-2 columns: `python -m data.state_snapshot_builder --seasons 2018 2019 2020 2021 2022 2023 2024 2025`
> 4. Retrain: `python scripts\retrain_after_features.py`
> 5. Inspect `artifacts\audit_report.json` — phase-2 features should show ablation delta vs phase-1-only baseline.

---

## What's NOT in this plan (intentionally)

- **Pitcher-handedness-specific xwOBA splits** (option B from #2 platoon question) — defer to #2.5 if binary flag underperforms
- **Bullpen leverage features** (sub-project #3) — separate brainstorming cycle
- **Weather + extras-inning model** (sub-project #4)
- **Running the actual snapshot regeneration / retrain** — operator's local commands

---

## Spec coverage check

| Spec section | Implementation task |
|---|---|
| §1 Architecture | Tasks 1–11 (all files mapped) |
| §2 Features (30→35) | Tasks 6, 7 |
| §3 Snapshot schema (29→36) | Task 5 |
| §4 Live data (lineup + current batter) | Task 4, 8 |
| §5 Audit gates | Task 10 (constant); audit framework already exists from #1 |
| §6 Error handling | Tasks 4 (LineupError), 8 (try/except + impute), 11 (atomic write) |
| §7 Testing — unit | Tasks 1, 2, 3, 4 |
| §7 Testing — integration | Task 12 |
| §7 Manual smoke | Task 13 step 3 |
| §8 Operational (cron) | Task 11 |
