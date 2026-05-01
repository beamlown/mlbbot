# MLB Model Signal Quality #3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 5 bullpen-and-leverage features to the model (home/away reliever quality, home/away rolling bullpen avg, static leverage index). Feature count grows 35 → 40.

**Architecture:** Parallels #1.5 (aggregate → point-in-time) and #2 (builder + live lookup + daily refresh) patterns. Relief-FIP comes from Statcast with `ip<4.0` filter (inverse of starter filter); leverage index is a one-time static table built from historical RE24 swings.

**Tech Stack:** Python 3.11, pandas/pyarrow, pytest, Windows Task Scheduler.

**Spec:** `docs/superpowers/specs/2026-04-19-mlb-model-signal-quality-3-design.md`

---

## File Map

### New
| Path | Responsibility |
|---|---|
| `data/foundation/statcast_reliever_aggregator.py` | Per-(pitcher, game) relief-FIP from Statcast (IP<4.0 filter) |
| `data/foundation/reliever_quality_builder.py` | Point-in-time hybrid relief-FIP- per (pitcher_id, as_of_date) |
| `data/foundation/bullpen_aggregator.py` | Rolling 30-day team bullpen avg FIP- (top-8 relievers) |
| `data/foundation/leverage_index_builder.py` | Static table from historical RE24 swings |
| `sports/mlb/reliever_quality_live.py` | `(pitcher_id, date) → reliever quality` |
| `sports/mlb/bullpen_quality_live.py` | `(team, date) → bullpen avg quality` |
| `sports/mlb/leverage_index_live.py` | `(inning, outs, base_state, score_diff) → LI` |
| `scripts/refresh_reliever_quality_daily.py` | Daily incremental |
| `scripts/refresh_bullpen_quality_daily.py` | Daily incremental |
| `scripts/cron/run_refresh_reliever_quality_daily.bat` | Windows wrapper |
| `scripts/cron/run_refresh_bullpen_quality_daily.bat` | Windows wrapper |
| `tests/test_statcast_reliever_aggregator.py` | Unit |
| `tests/test_reliever_quality_builder.py` | Unit (leak guard) |
| `tests/test_reliever_quality_live.py` | Unit |
| `tests/test_bullpen_aggregator.py` | Unit |
| `tests/test_bullpen_quality_live.py` | Unit |
| `tests/test_leverage_index_builder.py` | Unit |
| `tests/test_leverage_index_live.py` | Unit |

### Modified
| Path | Change |
|---|---|
| `data/feature_store.py` | FEATURE_COLUMNS 35→40 + phase-3 enrichment block |
| `sports/mlb/winprob_inference.py` | `phase3_extras` param, 5 new features |
| `integration/recommendation_api.py` | Build phase3_extras, wire to inference |
| `core/selfcheck.py` | `EXPECTED_FEATURE_COUNT = 40` |
| `models/audit_features.py` | `PHASE3_NEW_FEATURES` constant |
| `scripts/cron/install_scheduled_tasks.bat` | +2 tasks (6 total) |
| `docs/runbook.md` | Document new cron tasks |
| `tests/integration/test_full_pipeline.py` | Extend with reliever path |

---

## Task 1: Statcast reliever aggregator

**Files:**
- Create: `C:/Users/johnny/Desktop/mlb_model/data/foundation/statcast_reliever_aggregator.py`
- Create: `C:/Users/johnny/Desktop/mlb_model/tests/test_statcast_reliever_aggregator.py`

- [ ] **Step 1 (TDD): Write failing test**

`tests/test_statcast_reliever_aggregator.py`:

```python
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
    assert out.empty  # 14 outs = 4.67 IP → starter

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
```

- [ ] **Step 2: Run, confirm fails**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_statcast_reliever_aggregator.py -v
```

- [ ] **Step 3: Implement `data/foundation/statcast_reliever_aggregator.py`**

```python
"""
data/foundation/statcast_reliever_aggregator.py

Aggregate Statcast pitches into per-(pitcher, game) relief-FIP rows.
Uses the EXISTING pitcher aggregation logic but filters to IP<4.0 (relief outings).

Output schema:
    pitcher_id (int), game_pk, game_date (date),
    ip, k, bb, hr, fip, season
"""
from __future__ import annotations
import logging
from pathlib import Path
import pandas as pd

from data.foundation.statcast_pitcher_aggregator import aggregate_per_pitcher_per_game

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("data/features/reliever_quality.parquet")
RELIEF_IP_MAX = 4.0


def aggregate_reliever_per_game(pitches: pd.DataFrame) -> pd.DataFrame:
    """Aggregate via pitcher aggregator, then filter to relief outings only."""
    full = aggregate_per_pitcher_per_game(pitches)
    if full.empty:
        return full
    return full[full["ip"] < RELIEF_IP_MAX].reset_index(drop=True)


def aggregate_from_statcast_dir(statcast_dir: Path = Path("data/raw/statcast"),
                                seasons: list[int] | None = None) -> pd.DataFrame:
    """Read Statcast parquets, filter to relief outings, return combined DataFrame."""
    import pyarrow.parquet as pq
    parquets = sorted(statcast_dir.glob("*.parquet"))
    if not parquets:
        raise FileNotFoundError(f"No Statcast parquets in {statcast_dir}")
    frames = []
    for p in parquets:
        if seasons is not None:
            yr = None
            for tok in p.stem.replace("-", "_").split("_"):
                if tok.isdigit() and len(tok) == 4:
                    yr = int(tok); break
            if yr is not None and yr not in seasons:
                continue
        try:
            schema_cols = pq.read_schema(p).names
        except Exception as e:
            logger.warning("skipping unreadable parquet %s: %s", p.name, e)
            continue
        if "pitcher" not in schema_cols:
            continue
        df = pd.read_parquet(p, columns=["pitcher", "game_pk", "game_date", "events"])
        if df.empty:
            continue
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["pitcher_id", "game_pk", "game_date",
                                     "ip", "k", "bb", "hr", "fip", "season"])
    return aggregate_reliever_per_game(pd.concat(frames, ignore_index=True))
```

- [ ] **Step 4: Run tests (3/3 PASSED)**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_statcast_reliever_aggregator.py -v
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/data/foundation/statcast_reliever_aggregator.py mlb_model/tests/test_statcast_reliever_aggregator.py && git commit -m "mlb_model: add Statcast reliever aggregator (relief-FIP, IP<4) (#3)"
```

---

## Task 2: Reliever quality builder (point-in-time)

**Files:**
- Create: `C:/Users/johnny/Desktop/mlb_model/data/foundation/reliever_quality_builder.py`
- Create: `C:/Users/johnny/Desktop/mlb_model/tests/test_reliever_quality_builder.py`

- [ ] **Step 1 (TDD): Write failing test**

`tests/test_reliever_quality_builder.py`:

```python
import pandas as pd
import pytest
from datetime import date
from data.foundation.reliever_quality_builder import (
    compute_reliever_quality_pointtime,
)

def _synthetic_relief():
    """Reliever with 20 relief appearances in 2024, ERA-ish FIP of 3.0."""
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

def test_midseason_below_average_yields_good_quality():
    h = _synthetic_relief()
    out = compute_reliever_quality_pointtime(h, snapshot_dates=[date(2024, 9, 1)])
    r = out[out.pitcher_id == "R1"].iloc[0]
    # FIP 3.0 vs league 4.0 → FIP- = 75 (lower = better)
    assert r.reliever_quality < 100
    assert r.n_outings_std > 0
```

- [ ] **Step 2: Run, confirm fails**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_reliever_quality_builder.py -v
```

- [ ] **Step 3: Implement `data/foundation/reliever_quality_builder.py`**

```python
"""
data/foundation/reliever_quality_builder.py

Point-in-time reliever quality (FIP-) per (pitcher_id, as_of_date).

For each (pitcher_id, as_of_date) we compute:
    reliever_quality: hybrid FIP- (0.6 * current_STD + 0.4 * prior_season),
                      regressed toward league mean by IP. 100 = league avg,
                      lower better.
    n_outings_std:    relief outings in current season up to (not including) as_of_date

CRITICAL: only outings with game_date < as_of_date contribute.
"""
from __future__ import annotations
import logging
from datetime import date
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("data/features/reliever_quality.parquet")
LEAGUE_FIP_DEFAULT = 4.00
REGRESSION_IP = 25.0    # reliever IP regression (lower than starters — smaller sample)
PRIOR_WEIGHT = 0.4


def _hybrid_fip_minus(prior_fip: float | None, std_fip: float | None,
                      std_ip: float, league_fip: float = LEAGUE_FIP_DEFAULT) -> float:
    has_prior = prior_fip is not None and not pd.isna(prior_fip)
    has_std = std_fip is not None and not pd.isna(std_fip)
    if not has_prior and not has_std:
        return 100.0
    if not has_prior:
        raw = std_fip
    elif not has_std:
        raw = prior_fip
    else:
        raw = (1.0 - PRIOR_WEIGHT) * std_fip + PRIOR_WEIGHT * prior_fip
    weight = std_ip / (std_ip + REGRESSION_IP) if std_ip > 0 else 0.0
    regressed = weight * raw + (1.0 - weight) * league_fip
    return (regressed / league_fip) * 100.0


def compute_reliever_quality_pointtime(
    history: pd.DataFrame,
    snapshot_dates: list[date] | None = None,
) -> pd.DataFrame:
    """
    history columns: pitcher_id, game_date, ip, fip, season
    Returns: pitcher_id, as_of_date, reliever_quality, n_outings_std
    """
    cols = ["pitcher_id", "as_of_date", "reliever_quality", "n_outings_std"]
    if history.empty:
        return pd.DataFrame(columns=cols)

    h = history.copy()
    h["game_date"] = pd.to_datetime(h["game_date"]).dt.date

    if snapshot_dates is None:
        snapshot_dates = sorted(set(h["game_date"].tolist()))

    pitchers = h["pitcher_id"].unique()
    out_rows = []
    for pid in pitchers:
        ph = h[h["pitcher_id"] == pid]
        for as_of in snapshot_dates:
            past = ph[ph["game_date"] < as_of]
            if past.empty:
                continue
            cur_season = as_of.year
            std = past[past["season"] == cur_season]
            prior = past[past["season"] == cur_season - 1]
            std_ip = float(std["ip"].sum()) if not std.empty else 0.0
            std_fip = float((std["fip"] * std["ip"]).sum() / std_ip) if std_ip > 0 else None
            prior_ip = float(prior["ip"].sum()) if not prior.empty else 0.0
            prior_fip = float((prior["fip"] * prior["ip"]).sum() / prior_ip) if prior_ip > 0 else None
            q = _hybrid_fip_minus(prior_fip, std_fip, std_ip)
            out_rows.append({
                "pitcher_id": pid,
                "as_of_date": as_of,
                "reliever_quality": q,
                "n_outings_std": int(len(std)),
            })
    return pd.DataFrame(out_rows, columns=cols)


def build_from_statcast(seasons: list[int] | None = None) -> pd.DataFrame:
    from data.foundation.statcast_reliever_aggregator import aggregate_from_statcast_dir
    history = aggregate_from_statcast_dir(seasons=seasons)
    if history.empty:
        return pd.DataFrame(columns=["pitcher_id", "as_of_date", "reliever_quality", "n_outings_std"])
    history["pitcher_id"] = history["pitcher_id"].astype(str)
    return compute_reliever_quality_pointtime(
        history[["pitcher_id", "game_date", "ip", "fip", "season"]]
    )


def main() -> None:
    seasons = list(range(2018, 2026))
    df = build_from_statcast(seasons)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests (2/2 PASSED)**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_reliever_quality_builder.py -v
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/data/foundation/reliever_quality_builder.py mlb_model/tests/test_reliever_quality_builder.py && git commit -m "mlb_model: add point-in-time reliever quality builder (#3)"
```

---

## Task 3: Reliever quality live lookup

**Files:**
- Create: `C:/Users/johnny/Desktop/mlb_model/sports/mlb/reliever_quality_live.py`
- Create: `C:/Users/johnny/Desktop/mlb_model/tests/test_reliever_quality_live.py`

- [ ] **Step 1 (TDD): Write failing test**

```python
from datetime import date
import pandas as pd
import pytest
from sports.mlb.reliever_quality_live import (
    lookup_reliever_quality, _set_test_table, RelieverQuality,
)

@pytest.fixture(autouse=True)
def reset():
    yield
    _set_test_table(None)

def test_lookup_known():
    tbl = pd.DataFrame([{
        "pitcher_id": "R1", "as_of_date": date(2025, 7, 1),
        "reliever_quality": 85.0, "n_outings_std": 40,
    }])
    _set_test_table(tbl)
    q = lookup_reliever_quality("R1", date(2025, 7, 1))
    assert q.reliever_quality == pytest.approx(85.0)
    assert q.imputed is False

def test_unknown_imputes_100():
    _set_test_table(pd.DataFrame(columns=["pitcher_id", "as_of_date", "reliever_quality", "n_outings_std"]))
    q = lookup_reliever_quality("unknown", date(2025, 7, 1))
    assert q.reliever_quality == 100.0
    assert q.imputed is True

def test_falls_back_to_prior_date():
    tbl = pd.DataFrame([{
        "pitcher_id": "R1", "as_of_date": date(2025, 6, 1),
        "reliever_quality": 90.0, "n_outings_std": 20,
    }])
    _set_test_table(tbl)
    q = lookup_reliever_quality("R1", date(2025, 7, 1))
    assert q.reliever_quality == pytest.approx(90.0)
    assert q.imputed is False
```

- [ ] **Step 2: Run, confirm fails**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_reliever_quality_live.py -v
```

- [ ] **Step 3: Implement `sports/mlb/reliever_quality_live.py`**

```python
"""
sports/mlb/reliever_quality_live.py — Live (pitcher_id, date) → reliever_quality.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)
_TABLE: Optional[pd.DataFrame] = None
_TABLE_PATH = Path("data/features/reliever_quality.parquet")
LEAGUE_MEAN = 100.0


@dataclass
class RelieverQuality:
    reliever_quality: float
    n_outings_std: int
    imputed: bool


def _load_table() -> pd.DataFrame:
    global _TABLE
    if _TABLE is None:
        if _TABLE_PATH.exists():
            _TABLE = pd.read_parquet(_TABLE_PATH)
            _TABLE["as_of_date"] = pd.to_datetime(_TABLE["as_of_date"]).dt.date
        else:
            _TABLE = pd.DataFrame(columns=["pitcher_id", "as_of_date",
                                           "reliever_quality", "n_outings_std"])
    return _TABLE


def _set_test_table(df: Optional[pd.DataFrame]) -> None:
    global _TABLE
    _TABLE = df


def lookup_reliever_quality(pitcher_id: str, as_of: date) -> RelieverQuality:
    table = _load_table()
    if table.empty:
        return RelieverQuality(LEAGUE_MEAN, 0, imputed=True)
    rows = table[table["pitcher_id"] == str(pitcher_id)]
    if rows.empty:
        return RelieverQuality(LEAGUE_MEAN, 0, imputed=True)
    exact = rows[rows["as_of_date"] == as_of]
    if not exact.empty:
        r = exact.iloc[0]
    else:
        prior = rows[rows["as_of_date"] <= as_of].sort_values("as_of_date", ascending=False)
        if prior.empty:
            return RelieverQuality(LEAGUE_MEAN, 0, imputed=True)
        r = prior.iloc[0]
    return RelieverQuality(
        reliever_quality=float(r["reliever_quality"]),
        n_outings_std=int(r["n_outings_std"]),
        imputed=False,
    )
```

- [ ] **Step 4: Run tests (3/3 PASSED)**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_reliever_quality_live.py -v
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/sports/mlb/reliever_quality_live.py mlb_model/tests/test_reliever_quality_live.py && git commit -m "mlb_model: add reliever quality live lookup (#3)"
```

---

## Task 4: Bullpen rolling aggregator

**Files:**
- Create: `C:/Users/johnny/Desktop/mlb_model/data/foundation/bullpen_aggregator.py`
- Create: `C:/Users/johnny/Desktop/mlb_model/tests/test_bullpen_aggregator.py`

- [ ] **Step 1 (TDD): Write failing test**

```python
import pandas as pd
import pytest
from datetime import date, timedelta
from data.foundation.bullpen_aggregator import compute_bullpen_quality

def _synthetic_team_relief():
    """Team LAA with 3 relievers in last 30 days (limits test scope)."""
    rows = []
    for rid, fip in [("A", 2.5), ("B", 3.5), ("C", 5.0)]:
        for i in range(15):  # 15 appearances each = top-8 won't trigger trimming
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
    # Each pitcher: 15 IP, FIPs 2.5, 3.5, 5.0 → weighted = (2.5+3.5+5.0)/3 = 3.67
    # FIP- = 3.67/4.0 * 100 = 91.67
    assert 88 < row.bullpen_avg_quality < 95
    assert row.n_relievers == 3

def test_empty_returns_empty():
    out = compute_bullpen_quality(pd.DataFrame(), as_of=date(2025, 7, 1))
    assert out.empty
```

- [ ] **Step 2: Run, confirm fails**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_bullpen_aggregator.py -v
```

- [ ] **Step 3: Implement `data/foundation/bullpen_aggregator.py`**

```python
"""
data/foundation/bullpen_aggregator.py

Rolling team-level bullpen quality: weighted-mean relief-FIP across the
8 most-active relievers per team in a trailing N-day window.

Output: (team, as_of_date, bullpen_avg_quality, n_relievers)
"""
from __future__ import annotations
import logging
from datetime import date, timedelta
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("data/features/bullpen_quality.parquet")
LEAGUE_FIP = 4.0
TOP_N_RELIEVERS = 8
DEFAULT_WINDOW_DAYS = 30


def compute_bullpen_quality(
    history: pd.DataFrame,
    as_of: date,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> pd.DataFrame:
    """
    history columns: pitcher_id, team, game_date, ip, fip
    Returns one row per team: (team, as_of_date, bullpen_avg_quality, n_relievers).
    """
    cols = ["team", "as_of_date", "bullpen_avg_quality", "n_relievers"]
    if history.empty:
        return pd.DataFrame(columns=cols)

    h = history.copy()
    h["game_date"] = pd.to_datetime(h["game_date"]).dt.date
    window_start = as_of - timedelta(days=window_days)
    window = h[(h["game_date"] >= window_start) & (h["game_date"] < as_of)]
    if window.empty:
        return pd.DataFrame(columns=cols)

    rows = []
    for team, team_df in window.groupby("team"):
        # Top-N relievers by appearances
        counts = team_df.groupby("pitcher_id").size().sort_values(ascending=False)
        top_ids = counts.head(TOP_N_RELIEVERS).index.tolist()
        top_outings = team_df[team_df["pitcher_id"].isin(top_ids)]
        total_ip = float(top_outings["ip"].sum())
        if total_ip <= 0:
            continue
        weighted_fip = float((top_outings["fip"] * top_outings["ip"]).sum() / total_ip)
        bullpen_quality = (weighted_fip / LEAGUE_FIP) * 100.0
        rows.append({
            "team": team,
            "as_of_date": as_of,
            "bullpen_avg_quality": bullpen_quality,
            "n_relievers": len(top_ids),
        })
    return pd.DataFrame(rows, columns=cols)


def build_from_statcast(seasons: list[int] | None = None) -> pd.DataFrame:
    """Build bullpen quality rolling-30d snapshots at each unique game_date."""
    from data.foundation.statcast_reliever_aggregator import aggregate_from_statcast_dir
    import pyarrow.parquet as pq
    from pathlib import Path as _P

    history = aggregate_from_statcast_dir(seasons=seasons)
    if history.empty:
        return pd.DataFrame(columns=["team", "as_of_date", "bullpen_avg_quality", "n_relievers"])

    # Need to attach team — join to Statcast metadata
    # Re-read statcast for (game_pk → home_team / away_team) lookup + inning_topbot to
    # determine which team the pitcher was on
    statcast_dir = _P("data/raw/statcast")
    parquets = sorted(statcast_dir.glob("*.parquet"))
    team_frames = []
    for p in parquets:
        try:
            cols = pq.read_schema(p).names
        except Exception:
            continue
        if "pitcher" not in cols:
            continue
        df = pd.read_parquet(p, columns=["pitcher", "game_pk", "home_team",
                                         "away_team", "inning_topbot"])
        if df.empty:
            continue
        df["team"] = df.apply(
            lambda r: r["home_team"] if r["inning_topbot"] == "Top" else r["away_team"],
            axis=1,
        )
        team_frames.append(df[["pitcher", "game_pk", "team"]].drop_duplicates(
            subset=["pitcher", "game_pk"]))
    if not team_frames:
        return pd.DataFrame(columns=["team", "as_of_date", "bullpen_avg_quality", "n_relievers"])

    teams = pd.concat(team_frames, ignore_index=True)
    teams = teams.rename(columns={"pitcher": "pitcher_id"})
    teams["pitcher_id"] = teams["pitcher_id"].astype(str)
    history["pitcher_id"] = history["pitcher_id"].astype(str)
    merged = history.merge(teams, on=["pitcher_id", "game_pk"], how="left")
    merged = merged.dropna(subset=["team"])

    # Snapshot every unique date in the data
    snapshots = sorted(merged["game_date"].unique())
    out_frames = []
    for d in snapshots:
        bq = compute_bullpen_quality(merged, as_of=d)
        if not bq.empty:
            out_frames.append(bq)
    if not out_frames:
        return pd.DataFrame(columns=["team", "as_of_date", "bullpen_avg_quality", "n_relievers"])
    return pd.concat(out_frames, ignore_index=True)


def main() -> None:
    seasons = list(range(2018, 2026))
    df = build_from_statcast(seasons)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests (2/2 PASSED)**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_bullpen_aggregator.py -v
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/data/foundation/bullpen_aggregator.py mlb_model/tests/test_bullpen_aggregator.py && git commit -m "mlb_model: add rolling bullpen quality aggregator (#3)"
```

---

## Task 5: Bullpen quality live lookup

**Files:**
- Create: `C:/Users/johnny/Desktop/mlb_model/sports/mlb/bullpen_quality_live.py`
- Create: `C:/Users/johnny/Desktop/mlb_model/tests/test_bullpen_quality_live.py`

- [ ] **Step 1 (TDD): Write failing test**

```python
from datetime import date
import pandas as pd
import pytest
from sports.mlb.bullpen_quality_live import lookup_bullpen_quality, _set_test_table

@pytest.fixture(autouse=True)
def reset():
    yield
    _set_test_table(None)

def test_lookup_known():
    tbl = pd.DataFrame([{
        "team": "LAA", "as_of_date": date(2025, 7, 1),
        "bullpen_avg_quality": 88.0, "n_relievers": 8,
    }])
    _set_test_table(tbl)
    q = lookup_bullpen_quality("LAA", date(2025, 7, 1))
    assert q == pytest.approx(88.0)

def test_lookup_unknown_returns_100():
    _set_test_table(pd.DataFrame(columns=["team", "as_of_date", "bullpen_avg_quality", "n_relievers"]))
    assert lookup_bullpen_quality("XXX", date(2025, 7, 1)) == 100.0

def test_fallback_to_prior_date():
    tbl = pd.DataFrame([{
        "team": "LAA", "as_of_date": date(2025, 6, 1),
        "bullpen_avg_quality": 95.0, "n_relievers": 8,
    }])
    _set_test_table(tbl)
    assert lookup_bullpen_quality("LAA", date(2025, 7, 1)) == pytest.approx(95.0)
```

- [ ] **Step 2: Run, confirm fails**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_bullpen_quality_live.py -v
```

- [ ] **Step 3: Implement `sports/mlb/bullpen_quality_live.py`**

```python
"""sports/mlb/bullpen_quality_live.py — Live (team, date) → bullpen_avg_quality."""
from __future__ import annotations
import logging
from datetime import date
from pathlib import Path
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)
_TABLE: Optional[pd.DataFrame] = None
_TABLE_PATH = Path("data/features/bullpen_quality.parquet")
LEAGUE_MEAN = 100.0


def _load_table() -> pd.DataFrame:
    global _TABLE
    if _TABLE is None:
        if _TABLE_PATH.exists():
            _TABLE = pd.read_parquet(_TABLE_PATH)
            _TABLE["as_of_date"] = pd.to_datetime(_TABLE["as_of_date"]).dt.date
        else:
            _TABLE = pd.DataFrame(columns=["team", "as_of_date",
                                           "bullpen_avg_quality", "n_relievers"])
    return _TABLE


def _set_test_table(df: Optional[pd.DataFrame]) -> None:
    global _TABLE
    _TABLE = df


def lookup_bullpen_quality(team: str, as_of: date) -> float:
    table = _load_table()
    if table.empty:
        return LEAGUE_MEAN
    rows = table[table["team"] == team]
    if rows.empty:
        return LEAGUE_MEAN
    exact = rows[rows["as_of_date"] == as_of]
    if not exact.empty:
        return float(exact.iloc[0]["bullpen_avg_quality"])
    prior = rows[rows["as_of_date"] <= as_of].sort_values("as_of_date", ascending=False)
    if prior.empty:
        return LEAGUE_MEAN
    return float(prior.iloc[0]["bullpen_avg_quality"])
```

- [ ] **Step 4: Run tests (3/3 PASSED)**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_bullpen_quality_live.py -v
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/sports/mlb/bullpen_quality_live.py mlb_model/tests/test_bullpen_quality_live.py && git commit -m "mlb_model: add bullpen quality live lookup (#3)"
```

---

## Task 6: Leverage index builder (static table)

**Files:**
- Create: `C:/Users/johnny/Desktop/mlb_model/data/foundation/leverage_index_builder.py`
- Create: `C:/Users/johnny/Desktop/mlb_model/tests/test_leverage_index_builder.py`

- [ ] **Step 1 (TDD): Write failing test**

```python
import pandas as pd
import pytest
from data.foundation.leverage_index_builder import (
    build_leverage_table,
    _score_bucket,
)

def test_score_bucket():
    assert _score_bucket(0) == 0
    assert _score_bucket(2) == 2
    assert _score_bucket(-2) == -2
    assert _score_bucket(10) == 5    # clamped
    assert _score_bucket(-10) == -5

def test_build_produces_complete_table():
    """Synthetic game data → LI table covers all state combos seen."""
    rows = [
        {"inning": 1, "outs": 0, "base_state": 0, "score_diff": 0, "wp_swing_sq": 0.05},
        {"inning": 9, "outs": 2, "base_state": 7, "score_diff": 0, "wp_swing_sq": 0.80},
        {"inning": 5, "outs": 1, "base_state": 3, "score_diff": 1, "wp_swing_sq": 0.15},
    ]
    df = pd.DataFrame(rows)
    tbl = build_leverage_table(df)
    # Late-game tie with bases loaded should have higher LI than early game
    li_late = tbl[(tbl.inning == 9) & (tbl.outs == 2) & (tbl.base_state == 7) &
                  (tbl.score_bucket == 0)].iloc[0].leverage_index
    li_early = tbl[(tbl.inning == 1) & (tbl.outs == 0) & (tbl.base_state == 0) &
                   (tbl.score_bucket == 0)].iloc[0].leverage_index
    assert li_late > li_early
```

- [ ] **Step 2: Run, confirm fails**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_leverage_index_builder.py -v
```

- [ ] **Step 3: Implement `data/foundation/leverage_index_builder.py`**

```python
"""
data/foundation/leverage_index_builder.py

Build a static leverage-index table from historical game state→outcome data.

LI = (avg win-prob swing from this state)^2 / (mean win-prob swing squared overall).
We use squared swing so high-leverage states (big potential swings either way)
rank above states that are effectively locked.

Output schema: inning (1-12), outs (0-2), base_state (0-7), score_bucket (-5..+5),
              leverage_index (float, normalized to mean=1.0)
"""
from __future__ import annotations
import logging
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("data/features/leverage_index.parquet")


def _score_bucket(score_diff: int) -> int:
    """Clamp score_diff to [-5, 5]."""
    return max(-5, min(5, int(score_diff)))


def build_leverage_table(pa_wp_swings: pd.DataFrame) -> pd.DataFrame:
    """
    pa_wp_swings columns: inning (int), outs (int), base_state (int),
                          score_diff (int), wp_swing_sq (float, (delta P(home wins))**2)
    Returns one row per (inning, outs, base_state, score_bucket) with normalized LI.
    """
    cols = ["inning", "outs", "base_state", "score_bucket", "leverage_index"]
    if pa_wp_swings.empty:
        return pd.DataFrame(columns=cols)

    df = pa_wp_swings.copy()
    df["score_bucket"] = df["score_diff"].apply(_score_bucket)
    grouped = df.groupby(
        ["inning", "outs", "base_state", "score_bucket"]
    )["wp_swing_sq"].mean().reset_index()
    overall_mean = float(grouped["wp_swing_sq"].mean())
    if overall_mean <= 0:
        grouped["leverage_index"] = 1.0
    else:
        grouped["leverage_index"] = grouped["wp_swing_sq"] / overall_mean
    return grouped[cols]


def build_from_snapshots(snapshots_dir: Path = Path("data/features")) -> pd.DataFrame:
    """
    Derive PA-level WP swings from snapshot history.

    Heuristic: for each (inning, outs, base_state, score_diff) bin, compute
    empirical home-win rate vs. league baseline. LI is proportional to
    the variance of the win-prob update from that state.
    """
    parquets = sorted(snapshots_dir.glob("snapshots_*.parquet"))
    if not parquets:
        raise FileNotFoundError(f"No snapshot parquets in {snapshots_dir}")
    frames = []
    for p in parquets:
        df = pd.read_parquet(p, columns=["inning", "outs", "base_state",
                                         "score_diff", "home_won_final"])
        frames.append(df)
    snaps = pd.concat(frames, ignore_index=True)

    # Compute empirical win rate per (state) and use variance = p*(1-p) as a
    # proxy for WP swing squared (uncertainty peaks at p=0.5).
    snaps["score_bucket"] = snaps["score_diff"].apply(_score_bucket)
    g = snaps.groupby(
        ["inning", "outs", "base_state", "score_bucket"]
    )["home_won_final"].agg(["mean", "size"]).reset_index()
    g["wp_swing_sq"] = g["mean"] * (1 - g["mean"])
    # Filter low-sample bins (noisy)
    g = g[g["size"] >= 20]

    pa = g.rename(columns={"score_bucket": "score_diff"})[
        ["inning", "outs", "base_state", "score_diff", "wp_swing_sq"]]
    return build_leverage_table(pa)


def main() -> None:
    df = build_from_snapshots()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests (2/2 PASSED)**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_leverage_index_builder.py -v
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/data/foundation/leverage_index_builder.py mlb_model/tests/test_leverage_index_builder.py && git commit -m "mlb_model: add leverage index builder (static table) (#3)"
```

---

## Task 7: Leverage index live lookup

**Files:**
- Create: `C:/Users/johnny/Desktop/mlb_model/sports/mlb/leverage_index_live.py`
- Create: `C:/Users/johnny/Desktop/mlb_model/tests/test_leverage_index_live.py`

- [ ] **Step 1 (TDD): Write failing test**

```python
import pandas as pd
import pytest
from sports.mlb.leverage_index_live import lookup_leverage_index, _set_test_table

@pytest.fixture(autouse=True)
def reset():
    yield
    _set_test_table(None)

def test_lookup_exact():
    tbl = pd.DataFrame([{
        "inning": 9, "outs": 2, "base_state": 7, "score_bucket": 0,
        "leverage_index": 4.5,
    }])
    _set_test_table(tbl)
    li = lookup_leverage_index(inning=9, outs=2, base_state=7, score_diff=0)
    assert li == pytest.approx(4.5)

def test_lookup_unknown_state_returns_1():
    _set_test_table(pd.DataFrame(columns=["inning", "outs", "base_state",
                                          "score_bucket", "leverage_index"]))
    assert lookup_leverage_index(1, 0, 0, 0) == 1.0

def test_clamps_extreme_score_diff():
    tbl = pd.DataFrame([{
        "inning": 9, "outs": 2, "base_state": 7, "score_bucket": 5,
        "leverage_index": 0.1,   # blowout = low leverage
    }])
    _set_test_table(tbl)
    li = lookup_leverage_index(inning=9, outs=2, base_state=7, score_diff=20)
    assert li == pytest.approx(0.1)  # clamped to 5
```

- [ ] **Step 2: Run, confirm fails**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_leverage_index_live.py -v
```

- [ ] **Step 3: Implement `sports/mlb/leverage_index_live.py`**

```python
"""sports/mlb/leverage_index_live.py — Live LI lookup by game state."""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)
_TABLE: Optional[pd.DataFrame] = None
_TABLE_PATH = Path("data/features/leverage_index.parquet")
_LOOKUP: Optional[dict] = None


def _load_table() -> pd.DataFrame:
    global _TABLE, _LOOKUP
    if _TABLE is None:
        if _TABLE_PATH.exists():
            _TABLE = pd.read_parquet(_TABLE_PATH)
        else:
            _TABLE = pd.DataFrame(columns=["inning", "outs", "base_state",
                                           "score_bucket", "leverage_index"])
        _LOOKUP = None   # rebuild on next call
    return _TABLE


def _set_test_table(df: Optional[pd.DataFrame]) -> None:
    global _TABLE, _LOOKUP
    _TABLE = df
    _LOOKUP = None


def _build_lookup() -> dict:
    global _LOOKUP
    if _LOOKUP is None:
        tbl = _load_table()
        _LOOKUP = {
            (int(r["inning"]), int(r["outs"]), int(r["base_state"]), int(r["score_bucket"])):
                float(r["leverage_index"])
            for _, r in tbl.iterrows()
        }
    return _LOOKUP


def lookup_leverage_index(inning: int, outs: int, base_state: int, score_diff: int) -> float:
    """Return leverage index for this state. 1.0 (neutral) if unknown."""
    score_bucket = max(-5, min(5, int(score_diff)))
    lookup = _build_lookup()
    # Try exact; if inning >9, fall back to inning=9
    key = (int(inning), int(outs), int(base_state), score_bucket)
    if key in lookup:
        return lookup[key]
    if inning > 9:
        fallback = (9, int(outs), int(base_state), score_bucket)
        if fallback in lookup:
            return lookup[fallback]
    return 1.0
```

- [ ] **Step 4: Run tests (3/3 PASSED)**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_leverage_index_live.py -v
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/sports/mlb/leverage_index_live.py mlb_model/tests/test_leverage_index_live.py && git commit -m "mlb_model: add leverage index live lookup (#3)"
```

---

## Task 8: Feature store enrichment (35 → 40)

**Files:**
- Modify: `C:/Users/johnny/Desktop/mlb_model/data/feature_store.py`

- [ ] **Step 1: Extend FEATURE_COLUMNS**

Find the existing line:

```python
    "current_batter_xwoba_x_late",
]
```

REPLACE with:

```python
    "current_batter_xwoba_x_late",

    # ── PHASE-3 bullpen + leverage (added 2026-04-19) ────────────────────────
    "home_reliever_quality",
    "away_reliever_quality",
    "home_bullpen_avg_quality",
    "away_bullpen_avg_quality",
    "leverage_index",
]
```

- [ ] **Step 2: Extend enrichment function**

Find the existing `return out` at the end of `enrich_with_phase1_features` (which also handles phase-2). IMMEDIATELY BEFORE `return out`, INSERT:

```python
    # ── Phase-3: bullpen + leverage ──────────────────────────────────────────
    rq_path = FEATURE_DIR / "reliever_quality.parquet"
    bpq_path = FEATURE_DIR / "bullpen_quality.parquet"
    li_path = FEATURE_DIR / "leverage_index.parquet"

    # Reliever quality (per-pitcher, point-in-time)
    if rq_path.exists() and "home_pitcher_id" in out.columns and "date" in out.columns:
        rq = pd.read_parquet(rq_path)
        rq["as_of_date"] = pd.to_datetime(rq["as_of_date"]).dt.date
        rq["pitcher_id"] = rq["pitcher_id"].astype(str)
        rq_lookup = dict(zip(zip(rq["pitcher_id"], rq["as_of_date"]), rq["reliever_quality"]))
        join_dates = pd.to_datetime(out["date"]).dt.date
        def _rel(pid, d):
            return rq_lookup.get((str(pid), d), None)
        # Use reliever_quality if the pitcher is in the bullpen; else fall back to sp_quality
        out["home_reliever_quality"] = [
            (_rel(pid, d) if is_bp else out["home_sp_quality"].iloc[i]) or out["home_sp_quality"].iloc[i]
            for i, (pid, d, is_bp) in enumerate(zip(out["home_pitcher_id"], join_dates, out["home_is_bullpen"]))
        ]
        out["away_reliever_quality"] = [
            (_rel(pid, d) if is_bp else out["away_sp_quality"].iloc[i]) or out["away_sp_quality"].iloc[i]
            for i, (pid, d, is_bp) in enumerate(zip(out["away_pitcher_id"], join_dates, out["away_is_bullpen"]))
        ]
    else:
        out["home_reliever_quality"] = out.get("home_sp_quality", 100.0)
        out["away_reliever_quality"] = out.get("away_sp_quality", 100.0)

    # Bullpen avg quality
    if bpq_path.exists() and "home_team" in out.columns and "date" in out.columns:
        bpq = pd.read_parquet(bpq_path)
        bpq["as_of_date"] = pd.to_datetime(bpq["as_of_date"]).dt.date
        bpq_lookup = dict(zip(zip(bpq["team"], bpq["as_of_date"]), bpq["bullpen_avg_quality"]))
        join_dates = pd.to_datetime(out["date"]).dt.date
        def _bp(team, d):
            exact = bpq_lookup.get((team, d))
            return exact if exact is not None else 100.0
        out["home_bullpen_avg_quality"] = [_bp(t, d) for t, d in zip(out["home_team"], join_dates)]
        out["away_bullpen_avg_quality"] = [_bp(t, d) for t, d in zip(out["away_team"], join_dates)]
    else:
        out["home_bullpen_avg_quality"] = 100.0
        out["away_bullpen_avg_quality"] = 100.0

    # Leverage index
    if li_path.exists() and all(c in out.columns for c in ["inning", "outs", "base_state", "score_diff"]):
        li = pd.read_parquet(li_path)
        li_lookup = {
            (int(r["inning"]), int(r["outs"]), int(r["base_state"]), int(r["score_bucket"])):
                float(r["leverage_index"])
            for _, r in li.iterrows()
        }
        def _li(inn, o, bs, sd):
            bucket = max(-5, min(5, int(sd)))
            key = (int(inn), int(o), int(bs), bucket)
            if key in li_lookup:
                return li_lookup[key]
            if inn > 9:
                fb = (9, int(o), int(bs), bucket)
                if fb in li_lookup:
                    return li_lookup[fb]
            return 1.0
        out["leverage_index"] = [
            _li(inn, o, bs, sd) for inn, o, bs, sd in zip(
                out["inning"], out["outs"], out["base_state"], out["score_diff"]
            )
        ]
    else:
        out["leverage_index"] = 1.0

```

- [ ] **Step 3: Update NaN guard base_cols exclusion**

Find the existing base_cols exclusion that lists phase-1 and phase-2 columns. REPLACE with (adds phase-3):

```python
    base_cols = [c for c in FEATURE_COLUMNS if c not in (
        "home_sp_quality", "away_sp_quality",
        "home_sp_recent_form", "away_sp_recent_form",
        "sp_quality_diff", "park_run_factor",
        "park_run_factor_x_late", "pregame_prior_source",
        # phase-2
        "current_batter_xwoba", "next3_avg_xwoba", "lineup_avg_xwoba",
        "current_batter_platoon_advantage", "current_batter_xwoba_x_late",
        # phase-3
        "home_reliever_quality", "away_reliever_quality",
        "home_bullpen_avg_quality", "away_bullpen_avg_quality",
        "leverage_index",
    )]
```

- [ ] **Step 4: Smoke test**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -c "
from data.feature_store import FEATURE_COLUMNS, enrich_with_phase1_features
import pandas as pd
print('count:', len(FEATURE_COLUMNS))
assert len(FEATURE_COLUMNS) == 40
synthetic = pd.DataFrame({'pregame_logit': [0.0], 'score_diff': [0], 'late_game': [0.5], 'half': [0]})
out = enrich_with_phase1_features(synthetic)
for col in ['home_reliever_quality', 'away_reliever_quality',
            'home_bullpen_avg_quality', 'away_bullpen_avg_quality', 'leverage_index']:
    assert col in out.columns, f'missing {col}'
print('all 5 phase-3 columns present')
"
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/data/feature_store.py && git commit -m "mlb_model: extend feature_store with 5 phase-3 bullpen+leverage cols (#3)"
```

---

## Task 9: Inference path (35 → 40)

**Files:**
- Modify: `C:/Users/johnny/Desktop/mlb_model/sports/mlb/winprob_inference.py`
- Modify: `C:/Users/johnny/Desktop/mlb_model/tests/test_winprob_inference.py`

- [ ] **Step 1: Add `_PHASE3_FEATURE_NAMES`**

Find `_PHASE2_FEATURE_NAMES = (...)`. INSERT below:

```python
_PHASE3_FEATURE_NAMES = (
    "home_reliever_quality", "away_reliever_quality",
    "home_bullpen_avg_quality", "away_bullpen_avg_quality",
    "leverage_index",
)
```

- [ ] **Step 2: Extend `_build_feature_vector` signature**

Find:

```python
def _build_feature_vector(
    snapshot,
    pregame_win_prob: float,
    phase1_extras: dict | None = None,
    phase2_extras: dict | None = None,
) -> tuple[np.ndarray, dict[str, float], float]:
```

REPLACE with:

```python
def _build_feature_vector(
    snapshot,
    pregame_win_prob: float,
    phase1_extras: dict | None = None,
    phase2_extras: dict | None = None,
    phase3_extras: dict | None = None,
) -> tuple[np.ndarray, dict[str, float], float]:
```

- [ ] **Step 3: Add phase-3 features block**

Find the existing phase-2 block (after `feat["current_batter_xwoba_x_late"] = ...`). INSERT immediately after it, before `quality = 1.0`:

```python
    # Phase-3 bullpen + leverage
    p3 = phase3_extras or {}
    feat["home_reliever_quality"] = float(p3.get("home_reliever_quality", feat.get("home_sp_quality", 100.0)))
    feat["away_reliever_quality"] = float(p3.get("away_reliever_quality", feat.get("away_sp_quality", 100.0)))
    feat["home_bullpen_avg_quality"] = float(p3.get("home_bullpen_avg_quality", 100.0))
    feat["away_bullpen_avg_quality"] = float(p3.get("away_bullpen_avg_quality", 100.0))
    feat["leverage_index"] = float(p3.get("leverage_index", 1.0))
```

- [ ] **Step 4: Update `infer` and `infer_for_team` signatures**

Change `infer`:

```python
def infer(snapshot, pregame_win_prob: float = 0.54,
          phase1_extras: dict | None = None,
          phase2_extras: dict | None = None,
          phase3_extras: dict | None = None) -> InferenceResult:
    if _model is None or _calibrator is None:
        raise RuntimeError("Model artifacts not loaded.")
    X, feat_dict, quality = _build_feature_vector(snapshot, pregame_win_prob,
                                                   phase1_extras, phase2_extras, phase3_extras)
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
```

Change `infer_for_team`:

```python
def infer_for_team(snapshot, tracked_team, pregame_win_prob_home: float = 0.54,
                   phase1_extras: dict | None = None,
                   phase2_extras: dict | None = None,
                   phase3_extras: dict | None = None):
    from sports.mlb.team_normalizer import normalize
    result = infer(snapshot, pregame_win_prob_home, phase1_extras, phase2_extras, phase3_extras)
    tracked = normalize(tracked_team)
    p_tracked = result.p_home if tracked == snapshot.home_team else result.p_away
    return round(p_tracked, 6), result
```

- [ ] **Step 5: Add tests**

Append to `tests/test_winprob_inference.py`:

```python


def test_phase3_feature_names_count():
    from sports.mlb.winprob_inference import _PHASE3_FEATURE_NAMES
    assert len(_PHASE3_FEATURE_NAMES) == 5


def test_build_vector_with_phase3_extras():
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
        "home_reliever_quality","away_reliever_quality",
        "home_bullpen_avg_quality","away_bullpen_avg_quality","leverage_index",
    ]
    snap = SimpleNamespace(
        score_diff=0, inning=9, inning_half=1, outs=2, outs_elapsed=52,
        base_state=7, home_pitch_count=95, away_pitch_count=18,
        home_tto=3.0, away_tto=1.0, home_is_bullpen=False, away_is_bullpen=True,
    )
    p1 = {"home_sp_quality": 95, "away_sp_quality": 110,
          "home_sp_recent_form": 0, "away_sp_recent_form": 0,
          "park_run_factor": 1.0, "pregame_prior_source": 0,
          "home_sp_imputed": False, "away_sp_imputed": False}
    p2 = {"current_batter_xwoba": 100, "next3_avg_xwoba": 100,
          "lineup_avg_xwoba": 100, "current_batter_platoon_advantage": 0,
          "current_batter_imputed": False}
    p3 = {"home_reliever_quality": 95, "away_reliever_quality": 85,
          "home_bullpen_avg_quality": 95, "away_bullpen_avg_quality": 88,
          "leverage_index": 4.5}
    X, feat, q = wi._build_feature_vector(snap, 0.55, p1, p2, p3)
    assert X.shape == (1, 40)
    assert feat["leverage_index"] == 4.5
    assert feat["away_reliever_quality"] == 85
```

- [ ] **Step 6: Run tests (7/7 PASSED — 5 existing + 2 new)**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_winprob_inference.py -v
```

- [ ] **Step 7: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/sports/mlb/winprob_inference.py mlb_model/tests/test_winprob_inference.py && git commit -m "mlb_model: extend inference vector to 40 cols (phase-3) (#3)"
```

---

## Task 10: Wire phase-3 into recommendation_api

**Files:**
- Modify: `C:/Users/johnny/Desktop/mlb_model/integration/recommendation_api.py`

- [ ] **Step 1: Add imports**

Find the existing imports line:

```python
    from sports.mlb.lineup_live import fetch_live_lineup, LineupError
```

REPLACE with:

```python
    from sports.mlb.lineup_live import fetch_live_lineup, LineupError
    from sports.mlb.reliever_quality_live import lookup_reliever_quality
    from sports.mlb.bullpen_quality_live import lookup_bullpen_quality
    from sports.mlb.leverage_index_live import lookup_leverage_index
```

- [ ] **Step 2: Build phase3_extras**

Find the existing `phase2_extras = {...}` dict. Find its closing `}` — the line immediately AFTER the `p2_imputed = True` line (in the else branch). INSERT this block immediately after the phase-2 block:

```python

    # Phase-3: bullpen + leverage
    home_rel = lookup_reliever_quality(str(snap.home_pitcher_id), _gd) if snap.home_is_bullpen else None
    away_rel = lookup_reliever_quality(str(snap.away_pitcher_id), _gd) if snap.away_is_bullpen else None
    phase3_extras = {
        "home_reliever_quality": home_rel.reliever_quality if home_rel else phase1_extras["home_sp_quality"],
        "away_reliever_quality": away_rel.reliever_quality if away_rel else phase1_extras["away_sp_quality"],
        "home_bullpen_avg_quality": lookup_bullpen_quality(normalize(home_team), _gd),
        "away_bullpen_avg_quality": lookup_bullpen_quality(normalize(away_team), _gd),
        "leverage_index": lookup_leverage_index(
            inning=snap.inning, outs=snap.outs,
            base_state=snap.base_state, score_diff=snap.score_diff,
        ),
    }
```

- [ ] **Step 3: Update the infer_for_team call**

Find:

```python
        p_tracked, infer_result = infer_for_team(snap, tracked_team, pregame_prob, phase1_extras, phase2_extras)
```

REPLACE with:

```python
        p_tracked, infer_result = infer_for_team(snap, tracked_team, pregame_prob, phase1_extras, phase2_extras, phase3_extras)
```

- [ ] **Step 4: Surface phase-3 in reasons**

Find the existing phase-2 reasons block (the line `reasons.append(f"batter: xwoba=...")`). APPEND immediately after the `if p2_imputed: reasons.append("batter_imputed")` block, before `if gate_reasons:`:

```python

    # Phase-3 bullpen + leverage in reasons
    hrq = feat.get("home_reliever_quality", 100)
    arq = feat.get("away_reliever_quality", 100)
    li = feat.get("leverage_index", 1.0)
    reasons.append(f"pen: h={hrq:.0f} a={arq:.0f} | LI={li:.1f}")
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
cd C:/Users/johnny/Desktop && git add mlb_model/integration/recommendation_api.py && git commit -m "mlb_model: wire phase-3 bullpen+leverage into live recommendations (#3)"
```

---

## Task 11: Selfcheck bump

**Files:**
- Modify: `C:/Users/johnny/Desktop/mlb_model/core/selfcheck.py`

- [ ] **Step 1: Bump count**

Find:

```python
EXPECTED_FEATURE_COUNT = 35
```

REPLACE with:

```python
EXPECTED_FEATURE_COUNT = 40
```

- [ ] **Step 2: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/core/selfcheck.py && git commit -m "mlb_model: bump EXPECTED_FEATURE_COUNT to 40 (#3)"
```

---

## Task 12: Audit PHASE3 constant

**Files:**
- Modify: `C:/Users/johnny/Desktop/mlb_model/models/audit_features.py`

- [ ] **Step 1: Add constant**

Find:

```python
PHASE2_NEW_FEATURES = [
    "current_batter_xwoba",
    "next3_avg_xwoba",
    "lineup_avg_xwoba",
    "current_batter_platoon_advantage",
    "current_batter_xwoba_x_late",
]
```

INSERT below:

```python

PHASE3_NEW_FEATURES = [
    "home_reliever_quality",
    "away_reliever_quality",
    "home_bullpen_avg_quality",
    "away_bullpen_avg_quality",
    "leverage_index",
]
```

- [ ] **Step 2: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/models/audit_features.py && git commit -m "mlb_model: add PHASE3_NEW_FEATURES constant (#3)"
```

---

## Task 13: Daily refresh scripts + cron wrappers + installer

**Files:**
- Create: `C:/Users/johnny/Desktop/mlb_model/scripts/refresh_reliever_quality_daily.py`
- Create: `C:/Users/johnny/Desktop/mlb_model/scripts/refresh_bullpen_quality_daily.py`
- Create: `C:/Users/johnny/Desktop/mlb_model/scripts/cron/run_refresh_reliever_quality_daily.bat`
- Create: `C:/Users/johnny/Desktop/mlb_model/scripts/cron/run_refresh_bullpen_quality_daily.bat`
- Modify: `C:/Users/johnny/Desktop/mlb_model/scripts/cron/install_scheduled_tasks.bat`

- [ ] **Step 1: Implement `scripts/refresh_reliever_quality_daily.py`**

```python
"""scripts/refresh_reliever_quality_daily.py — Daily incremental refresh of reliever_quality.parquet."""
from __future__ import annotations
import logging
import os
from datetime import date, timedelta
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

RELIEVER_PATH = Path("data/features/reliever_quality.parquet")
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
    if "pitcher" not in schema_cols:
        return pd.DataFrame()
    df = pd.read_parquet(target_file, columns=["pitcher", "game_pk", "game_date", "events"])
    if df.empty:
        return pd.DataFrame()
    df["game_date"] = pd.to_datetime(df["game_date"]).dt.date
    return df[df["game_date"] == target_date]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    yesterday = date.today() - timedelta(days=1)
    pitches = _load_yesterdays_pitches(yesterday)
    if pitches.empty:
        print(f"No Statcast for {yesterday}; nothing to refresh.")
        return 0

    from data.foundation.statcast_reliever_aggregator import aggregate_reliever_per_game
    from data.foundation.reliever_quality_builder import compute_reliever_quality_pointtime

    new_history = aggregate_reliever_per_game(pitches)
    if new_history.empty:
        print(f"No relief outings on {yesterday}.")
        return 0
    new_history["pitcher_id"] = new_history["pitcher_id"].astype(str)

    existing = pd.read_parquet(RELIEVER_PATH) if RELIEVER_PATH.exists() else pd.DataFrame()

    yesterday_rq = compute_reliever_quality_pointtime(
        new_history[["pitcher_id", "game_date", "ip", "fip", "season"]],
        snapshot_dates=[yesterday + timedelta(days=1)],
    )
    if existing.empty:
        out = yesterday_rq
    else:
        out = pd.concat([existing, yesterday_rq], ignore_index=True)
        out = out.drop_duplicates(subset=["pitcher_id", "as_of_date"], keep="last")

    RELIEVER_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = RELIEVER_PATH.with_suffix(".parquet.tmp")
    out.to_parquet(tmp, index=False)
    os.replace(tmp, RELIEVER_PATH)
    print(f"Refreshed reliever_quality.parquet: +{len(yesterday_rq)} rows for {yesterday}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Implement `scripts/refresh_bullpen_quality_daily.py`**

```python
"""scripts/refresh_bullpen_quality_daily.py — Daily rolling bullpen avg refresh."""
from __future__ import annotations
import logging
import os
from datetime import date, timedelta
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

BULLPEN_PATH = Path("data/features/bullpen_quality.parquet")
RELIEVER_HISTORY_PATH = Path("data/features/reliever_quality_history.parquet")  # optional helper
STATCAST_DIR = Path("data/raw/statcast")


def main() -> int:
    """
    Refresh bullpen quality for today. Rebuilds from the full relief history in
    data/features/reliever_quality.parquet (via the bullpen_aggregator using
    Statcast for team mapping).
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    from data.foundation.bullpen_aggregator import build_from_statcast

    today = date.today()
    # Build from full Statcast history (bullpen is rolling 30d — needs recent data)
    df = build_from_statcast(seasons=list(range(today.year - 1, today.year + 1)))
    if df.empty:
        print("bullpen aggregator produced no rows")
        return 0

    BULLPEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = BULLPEN_PATH.with_suffix(".parquet.tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, BULLPEN_PATH)
    print(f"Wrote {len(df)} rows to {BULLPEN_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Implement `scripts/cron/run_refresh_reliever_quality_daily.bat`**

```
@echo off
REM Daily reliever quality refresh — Windows scheduled task `mlb-reliever-quality-daily`
cd /d "C:\Users\johnny\Desktop\mlb_model"
"C:\Users\johnny\AppData\Local\Python\pythoncore-3.14-64\python.exe" scripts\refresh_reliever_quality_daily.py >> logs\cron.log 2>&1
exit /b %ERRORLEVEL%
```

- [ ] **Step 4: Implement `scripts/cron/run_refresh_bullpen_quality_daily.bat`**

```
@echo off
REM Daily bullpen quality refresh — Windows scheduled task `mlb-bullpen-quality-daily`
cd /d "C:\Users\johnny\Desktop\mlb_model"
"C:\Users\johnny\AppData\Local\Python\pythoncore-3.14-64\python.exe" scripts\refresh_bullpen_quality_daily.py >> logs\cron.log 2>&1
exit /b %ERRORLEVEL%
```

- [ ] **Step 5: Update `install_scheduled_tasks.bat`**

Find:

```
echo Installing mlb-batter-quality-daily (08:30 daily)...
schtasks /Create /SC DAILY /TN mlb-batter-quality-daily /TR "C:\Users\johnny\Desktop\mlb_model\scripts\cron\run_refresh_batter_quality_daily.bat" /ST 08:30 /F
if errorlevel 1 goto :err
```

REPLACE with (inserts reliever + bullpen blocks):

```
echo Installing mlb-batter-quality-daily (08:30 daily)...
schtasks /Create /SC DAILY /TN mlb-batter-quality-daily /TR "C:\Users\johnny\Desktop\mlb_model\scripts\cron\run_refresh_batter_quality_daily.bat" /ST 08:30 /F
if errorlevel 1 goto :err

echo Installing mlb-reliever-quality-daily (08:15 daily)...
schtasks /Create /SC DAILY /TN mlb-reliever-quality-daily /TR "C:\Users\johnny\Desktop\mlb_model\scripts\cron\run_refresh_reliever_quality_daily.bat" /ST 08:15 /F
if errorlevel 1 goto :err

echo Installing mlb-bullpen-quality-daily (08:45 daily)...
schtasks /Create /SC DAILY /TN mlb-bullpen-quality-daily /TR "C:\Users\johnny\Desktop\mlb_model\scripts\cron\run_refresh_bullpen_quality_daily.bat" /ST 08:45 /F
if errorlevel 1 goto :err
```

Also find:

```
echo All 4 tasks installed. Verify with: schtasks /Query /TN mlb-elo-daily
```

REPLACE with:

```
echo All 6 tasks installed. Verify with: schtasks /Query /TN mlb-elo-daily
```

- [ ] **Step 6: Smoke test**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -c "
import py_compile
py_compile.compile('scripts/refresh_reliever_quality_daily.py', doraise=True)
py_compile.compile('scripts/refresh_bullpen_quality_daily.py', doraise=True)
print('OK')
"
```

- [ ] **Step 7: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/scripts/refresh_reliever_quality_daily.py mlb_model/scripts/refresh_bullpen_quality_daily.py mlb_model/scripts/cron/run_refresh_reliever_quality_daily.bat mlb_model/scripts/cron/run_refresh_bullpen_quality_daily.bat mlb_model/scripts/cron/install_scheduled_tasks.bat && git commit -m "mlb_model: add daily reliever + bullpen refresh + cron wrappers (#3)"
```

---

## Task 14: Integration test extension

**Files:**
- Modify: `C:/Users/johnny/Desktop/mlb_model/tests/integration/test_full_pipeline.py`

- [ ] **Step 1: Append a new test**

APPEND at the bottom of the existing file:

```python


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
```

- [ ] **Step 2: Run integration tests**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/integration/ -v
```

Expected: 5 PASSED (4 existing + 1 new).

- [ ] **Step 3: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/tests/integration/test_full_pipeline.py && git commit -m "mlb_model: extend integration tests with reliever path (#3)"
```

---

## Task 15: Final smoke + verification

**Files:** none

- [ ] **Step 1: Run all tests (~70+ expected)**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/ -v
```

- [ ] **Step 2: Import + count consistency**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -c "
from data.feature_store import FEATURE_COLUMNS
from sports.mlb.winprob_inference import _PHASE3_FEATURE_NAMES
from models.audit_features import PHASE1_NEW_FEATURES, PHASE2_NEW_FEATURES, PHASE3_NEW_FEATURES
from core.selfcheck import EXPECTED_FEATURE_COUNT
import integration.recommendation_api
print('FEATURE_COLUMNS:', len(FEATURE_COLUMNS))
print('PHASE1:', len(PHASE1_NEW_FEATURES))
print('PHASE2:', len(PHASE2_NEW_FEATURES))
print('PHASE3:', len(PHASE3_NEW_FEATURES))
print('EXPECTED:', EXPECTED_FEATURE_COUNT)
assert len(FEATURE_COLUMNS) == 40
assert EXPECTED_FEATURE_COUNT == 40
assert len(PHASE3_NEW_FEATURES) == 5
print('consistent: 22 + 8 + 5 + 5 = 40')
"
```

- [ ] **Step 3: Document operator follow-up**

Print:

> **Operator next steps:**
> 1. Bootstrap the 3 new parquets: `python -m data.foundation.leverage_index_builder && python -m data.foundation.reliever_quality_builder && python -m data.foundation.bullpen_aggregator`
> 2. Reinstall scheduled tasks: `scripts\cron\install_scheduled_tasks.bat` (now 6 tasks)
> 3. Retrain: `python scripts\retrain_after_features.py`
> 4. Inspect `artifacts\audit_report.json` — phase-3 features should show ablation delta vs phase-1+2 baseline.

---

## What's NOT in this plan (intentionally)

- **Closer-warming signal** (deferred to #3.5 if audit warrants)
- **Reliever freshness** (days-rest, back-to-back) — #3.5
- **Handedness splits for relievers** — #3.5
- **Sub-project #4** (weather + extras) — separate cycle

## Spec coverage check

| Spec section | Implementation task |
|---|---|
| §1 Architecture | Tasks 1-13 |
| §2 Features (35→40) | Tasks 8, 9 |
| §3 Relief-FIP aggregation | Task 1 |
| §4 Rolling bullpen | Task 4 |
| §5 Leverage index static table | Task 6 |
| §6 Audit gates | Task 12 |
| §7 Error handling | Tasks 3, 5, 7 (imputation), 13 (atomic) |
| §8 Testing (unit) | Tasks 1, 2, 3, 4, 5, 6, 7 |
| §8 Testing (integration) | Task 14 |
| §9 Operational cron | Task 13 |
