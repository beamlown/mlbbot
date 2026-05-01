# MLB Model Signal Quality #1.5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the phase-1 audit actually measure feature lift by giving offline snapshots the join keys they need (park_id, MLBAM-aligned pitcher_id), and add three daily scheduled triggers so the pipeline runs unattended.

**Architecture:** Replace pybaseball-name-keyed pitcher quality with Statcast-aggregated MLBAM-int-keyed pitcher quality (matches snapshot.home_pitcher_id natively). Add park_id + pregame_prior_source columns to snapshots via a static team→park map. Schedule 3 daily Claude Code triggers (Elo, sharp odds, pitcher quality) via the superpowers:schedule skill.

**Tech Stack:** Python 3.11, pandas/pyarrow, pytest, superpowers:schedule (Claude Code remote triggers).

**Spec:** `docs/superpowers/specs/2026-04-19-mlb-model-signal-quality-1.5-design.md`

---

## File Map

### New files
| Path | Responsibility |
|---|---|
| `sports/mlb/parks.py` | TEAM_TO_PARK static map (MLB abbrev → retrosheet ParkID) + helper |
| `data/foundation/statcast_pitcher_aggregator.py` | Aggregate Statcast pitches → per-(pitcher_id, game_pk) FIP |
| `scripts/refresh_pitcher_quality_daily.py` | Incremental: yesterday's Statcast → append to pitcher_quality.parquet |
| `tests/test_parks.py` | Unit |
| `tests/test_statcast_pitcher_aggregator.py` | Unit (FIP math, edge cases) |

### Modified files
| Path | Change |
|---|---|
| `data/foundation/pitcher_quality_builder.py` | Add `build_from_statcast()`; mark `build_from_pybaseball` DEPRECATED (don't delete) |
| `data/state_snapshot_builder.py` | Emit `park_id` + `pregame_prior_source` columns |
| `tests/integration/test_full_pipeline.py` | Extend with statcast-aggregator path |

### Remote triggers (no files; created via skill)
| Trigger | Cron (UTC) | Runs |
|---|---|---|
| `mlb-elo-daily` | `0 11 * * *` | `python scripts/update_elo_daily.py` |
| `mlb-pitcher-quality-daily` | `0 13 * * *` | `python scripts/refresh_pitcher_quality_daily.py` |
| `mlb-sharp-odds-daily` | `0 14 * * *` | `python scripts/update_sharp_odds_daily.py` |

---

## Task 1: TEAM_TO_PARK static map

**Files:**
- Create: `C:/Users/johnny/Desktop/mlb_model/sports/mlb/parks.py`
- Create: `C:/Users/johnny/Desktop/mlb_model/tests/test_parks.py`

- [ ] **Step 1: Write the failing test**

`tests/test_parks.py`:

```python
import pytest
from sports.mlb.parks import TEAM_TO_PARK, lookup_park_id, ALL_TEAMS

def test_every_team_has_park():
    for team in ALL_TEAMS:
        assert team in TEAM_TO_PARK, f"{team} missing from TEAM_TO_PARK"
        assert TEAM_TO_PARK[team], f"{team} has empty park_id"

def test_lookup_known_team():
    assert lookup_park_id("COL") == "DEN02"
    assert lookup_park_id("LAD") == "LOS03"
    assert lookup_park_id("BOS") == "BOS07"

def test_lookup_unknown_team_returns_unknown_string():
    assert lookup_park_id("XYZ") == "unknown"
    assert lookup_park_id("") == "unknown"

def test_lookup_normalizes_case():
    assert lookup_park_id("col") == "DEN02"
    assert lookup_park_id("Lad") == "LOS03"
```

- [ ] **Step 2: Run test, confirm it fails**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_parks.py -v
```
Expected: ImportError on `sports.mlb.parks`.

- [ ] **Step 3: Implement `sports/mlb/parks.py`**

Exact content:

```python
"""
sports/mlb/parks.py — Static MLB team-abbreviation → retrosheet ParkID map.

Used by data/state_snapshot_builder.py to label each snapshot's park_id so the
phase-1 enrichment can join to data/features/park_factors.parquet (which is
keyed on retrosheet ParkIDs).

Best-effort 2026 mapping. If a team relocates mid-season, update this map and
re-run the snapshot builder. Unknown teams resolve to "unknown" → live park
factor lookup falls back to neutral 1.0.
"""
from __future__ import annotations

# 30 MLB franchises, abbreviations as used in the snapshot tables (Statcast/ESPN).
# Values are retrosheet ParkIDs (verify against data/raw/retrosheet for edge cases).
TEAM_TO_PARK: dict[str, str] = {
    # AL East
    "BAL": "BAL12",   # Camden Yards
    "BOS": "BOS07",   # Fenway Park
    "NYY": "NYC21",   # Yankee Stadium (current)
    "TBR": "STP01",   # Tropicana Field
    "TB":  "STP01",
    "TOR": "TOR02",   # Rogers Centre

    # AL Central
    "CHW": "CHI12",   # Guaranteed Rate / Rate Field
    "CWS": "CHI12",
    "CLE": "CLE08",   # Progressive Field
    "DET": "DET05",   # Comerica Park
    "KCR": "KAN06",   # Kauffman Stadium
    "KC":  "KAN06",
    "MIN": "MIN04",   # Target Field

    # AL West
    "ATH": "OAK01",   # Athletics — Oakland Coliseum (placeholder; mid-2025+ moves to Sacramento)
    "OAK": "OAK01",
    "HOU": "HOU03",   # Minute Maid / Daikin Park
    "LAA": "ANA01",   # Angel Stadium
    "SEA": "SEA03",   # T-Mobile Park
    "TEX": "ARL02",   # Globe Life Field

    # NL East
    "ATL": "ATL03",   # Truist Park
    "MIA": "MIA02",   # loanDepot park
    "NYM": "NYC20",   # Citi Field
    "PHI": "PHI13",   # Citizens Bank Park
    "WSH": "WAS11",   # Nationals Park
    "WAS": "WAS11",

    # NL Central
    "CHC": "CHI11",   # Wrigley Field
    "CIN": "CIN09",   # Great American Ball Park
    "MIL": "MIL06",   # American Family Field
    "PIT": "PIT08",   # PNC Park
    "STL": "STL10",   # Busch Stadium

    # NL West
    "ARI": "PHO01",   # Chase Field
    "COL": "DEN02",   # Coors Field
    "LAD": "LOS03",   # Dodger Stadium
    "SDP": "SAN02",   # Petco Park
    "SD":  "SAN02",
    "SFG": "SFO03",   # Oracle Park
    "SF":  "SFO03",
}

# Canonical 30-team set (using preferred abbreviation per franchise)
ALL_TEAMS: list[str] = [
    "BAL", "BOS", "NYY", "TBR", "TOR",
    "CHW", "CLE", "DET", "KCR", "MIN",
    "ATH", "HOU", "LAA", "SEA", "TEX",
    "ATL", "MIA", "NYM", "PHI", "WSH",
    "CHC", "CIN", "MIL", "PIT", "STL",
    "ARI", "COL", "LAD", "SDP", "SFG",
]


def lookup_park_id(team_abbrev: str) -> str:
    """Return retrosheet ParkID for a team. 'unknown' if not in map."""
    if not team_abbrev:
        return "unknown"
    return TEAM_TO_PARK.get(team_abbrev.upper(), "unknown")
```

- [ ] **Step 4: Run tests, confirm 4/4 PASSED**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_parks.py -v
```
Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/sports/mlb/parks.py mlb_model/tests/test_parks.py && git commit -m "mlb_model: add TEAM_TO_PARK static map (#1.5)"
```

---

## Task 2: Statcast pitcher aggregator

**Files:**
- Create: `C:/Users/johnny/Desktop/mlb_model/data/foundation/statcast_pitcher_aggregator.py`
- Create: `C:/Users/johnny/Desktop/mlb_model/tests/test_statcast_pitcher_aggregator.py`

- [ ] **Step 1: Write the failing test**

`tests/test_statcast_pitcher_aggregator.py`:

```python
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
```

- [ ] **Step 2: Run test, confirm fails**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_statcast_pitcher_aggregator.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `data/foundation/statcast_pitcher_aggregator.py`**

Exact content:

```python
"""
data/foundation/statcast_pitcher_aggregator.py

Aggregate Statcast pitch-by-pitch data into per-(pitcher_id, game_pk) FIP rows.
Output is the input format expected by
data.foundation.pitcher_quality_builder.compute_pitcher_quality_pointtime.

Statcast `events` field values used:
  out events (1 out each): generic_out, field_out, force_out, sac_fly, sac_bunt,
                           grounded_into_double_play (counts 2 outs in real life
                           but Statcast emits 1 event row), fielders_choice_out,
                           strikeout, strikeout_double_play (2 outs)
  K events:                strikeout, strikeout_double_play
  BB events:               walk, hit_by_pitch
  HR event:                home_run

For simplicity we count outs by counting events in _OUT_EVENTS (one event = one
out). Edge case: strikeout_double_play and grounded_into_double_play are 2 outs
each — handled explicitly with multipliers.
"""
from __future__ import annotations
import logging
import math
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("data/features/pitcher_quality.parquet")

_K_EVENTS = {"strikeout", "strikeout_double_play"}
_BB_EVENTS = {"walk", "hit_by_pitch"}

# Each entry maps event → outs recorded
_OUT_EVENTS = {
    "field_out": 1,
    "force_out": 1,
    "sac_fly": 1,
    "sac_fly_double_play": 2,
    "sac_bunt": 1,
    "sac_bunt_double_play": 2,
    "fielders_choice_out": 1,
    "fielders_choice": 1,
    "grounded_into_double_play": 2,
    "double_play": 2,
    "triple_play": 3,
    "strikeout": 1,
    "strikeout_double_play": 2,
    "other_out": 1,
    "caught_stealing_2b": 0,   # not pitcher's
    "caught_stealing_3b": 0,
    "caught_stealing_home": 0,
    "pickoff_1b": 0,
    "pickoff_2b": 0,
    "pickoff_3b": 0,
}


def _compute_fip(ip: float, hr: int, bb: int, k: int, constant: float = 3.2) -> float:
    """Classic FIP. Returns NaN if ip == 0."""
    if ip <= 0:
        return float("nan")
    return (13 * hr + 3 * bb - 2 * k) / ip + constant


def aggregate_per_pitcher_per_game(pitches: pd.DataFrame) -> pd.DataFrame:
    """
    pitches columns required: pitcher (int MLBAM ID), game_pk, game_date, events
    Returns: DataFrame with columns
        pitcher_id (int), game_pk, game_date (date), ip, k, bb, hr, fip, season
    Rows where events is NaN/null are ignored (they're intra-PA pitches without
    a terminating event).
    """
    if pitches.empty:
        return pd.DataFrame(columns=["pitcher_id", "game_pk", "game_date",
                                     "ip", "k", "bb", "hr", "fip", "season"])

    df = pitches.copy()
    df = df.dropna(subset=["pitcher", "events"])
    if df.empty:
        return pd.DataFrame(columns=["pitcher_id", "game_pk", "game_date",
                                     "ip", "k", "bb", "hr", "fip", "season"])

    df["events"] = df["events"].astype(str)
    df["outs"] = df["events"].map(_OUT_EVENTS).fillna(0).astype(int)
    df["is_k"] = df["events"].isin(_K_EVENTS).astype(int)
    df["is_bb"] = df["events"].isin(_BB_EVENTS).astype(int)
    df["is_hr"] = (df["events"] == "home_run").astype(int)

    grouped = df.groupby(["pitcher", "game_pk", "game_date"], dropna=False).agg(
        outs=("outs", "sum"),
        k=("is_k", "sum"),
        bb=("is_bb", "sum"),
        hr=("is_hr", "sum"),
    ).reset_index()

    grouped = grouped.rename(columns={"pitcher": "pitcher_id"})
    grouped["pitcher_id"] = grouped["pitcher_id"].astype(int)
    grouped["ip"] = grouped["outs"] / 3.0
    grouped["fip"] = grouped.apply(
        lambda r: _compute_fip(r["ip"], r["hr"], r["bb"], r["k"]), axis=1
    )
    grouped["game_date"] = pd.to_datetime(grouped["game_date"]).dt.date
    grouped["season"] = pd.to_datetime(grouped["game_date"]).dt.year if False else \
        pd.Series([d.year for d in grouped["game_date"]])

    return grouped[["pitcher_id", "game_pk", "game_date",
                    "ip", "k", "bb", "hr", "fip", "season"]]


def aggregate_from_statcast_dir(statcast_dir: Path = Path("data/raw/statcast"),
                                seasons: list[int] | None = None) -> pd.DataFrame:
    """Read all Statcast monthly parquets, aggregate, return combined DataFrame."""
    parquets = sorted(statcast_dir.glob("*.parquet"))
    if not parquets:
        raise FileNotFoundError(f"No Statcast parquets in {statcast_dir}")
    frames = []
    for p in parquets:
        df = pd.read_parquet(p, columns=["pitcher", "game_pk", "game_date", "events"])
        if seasons is not None:
            yr_in_filename = None
            for tok in p.stem.replace("-", "_").split("_"):
                if tok.isdigit() and len(tok) == 4:
                    yr_in_filename = int(tok); break
            if yr_in_filename is not None and yr_in_filename not in seasons:
                continue
        frames.append(df)
    pitches = pd.concat(frames, ignore_index=True)
    return aggregate_per_pitcher_per_game(pitches)
```

- [ ] **Step 4: Run tests, confirm 4/4 PASSED**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_statcast_pitcher_aggregator.py -v
```
Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/data/foundation/statcast_pitcher_aggregator.py mlb_model/tests/test_statcast_pitcher_aggregator.py && git commit -m "mlb_model: add Statcast pitcher aggregator (per-game FIP) (#1.5)"
```

---

## Task 3: Add `build_from_statcast` to pitcher_quality_builder

**Files:**
- Modify: `C:/Users/johnny/Desktop/mlb_model/data/foundation/pitcher_quality_builder.py`

- [ ] **Step 1: Read the current file to understand structure**

```bash
cd C:/Users/johnny/Desktop/mlb_model && head -30 data/foundation/pitcher_quality_builder.py
```

You should see `OUTPUT_PATH = Path("data/features/pitcher_quality.parquet")` near the top, and `build_from_pybaseball(seasons)` + `main()` near the bottom.

- [ ] **Step 2: Add a deprecation banner above `build_from_pybaseball`**

Find the line `def build_from_pybaseball(seasons: list[int]) -> pd.DataFrame:` and INSERT this comment block immediately above it:

```python
# DEPRECATED — use build_from_statcast instead. The pybaseball loader keys on
# pitcher names, which don't match snapshot.home_pitcher_id (Statcast int IDs).
# This function is preserved for legacy callers but should not be used in the
# main pipeline. See sub-project #1.5 design doc for context.
```

- [ ] **Step 3: Add new `build_from_statcast` function**

Insert this AFTER the existing `def build_from_pybaseball(...)` function, BEFORE the `def main()` definition:

```python
def build_from_statcast(seasons: list[int] | None = None) -> pd.DataFrame:
    """
    Build the point-in-time pitcher quality table from local Statcast pitches.
    Uses MLBAM int pitcher IDs that match snapshot.home_pitcher_id natively.

    Pipeline: Statcast pitches → aggregate to per-game FIP →
              compute_pitcher_quality_pointtime() → output parquet rows.
    """
    from data.foundation.statcast_pitcher_aggregator import aggregate_from_statcast_dir
    starts = aggregate_from_statcast_dir(seasons=seasons)
    # Keep only rows with non-NaN FIP and at least 4 IP (starter heuristic)
    starts = starts[starts["fip"].notna() & (starts["ip"] >= 4.0)].copy()
    starts["pitcher_id"] = starts["pitcher_id"].astype(str)   # store as string for parquet stability
    return compute_pitcher_quality_pointtime(starts[["pitcher_id", "game_date", "ip", "fip", "season"]])
```

- [ ] **Step 4: Replace `main()` to use the new builder**

Find the existing `def main():` block. Replace its body with:

```python
def main() -> None:
    seasons = list(range(2018, 2026))
    df = build_from_statcast(seasons)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUTPUT_PATH}")
```

- [ ] **Step 5: Smoke test the import**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -c "
from data.foundation.pitcher_quality_builder import build_from_statcast, build_from_pybaseball, compute_pitcher_quality_pointtime
print('all 3 callables imported OK')
"
```
Expected: `all 3 callables imported OK`.

- [ ] **Step 6: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/data/foundation/pitcher_quality_builder.py && git commit -m "mlb_model: add build_from_statcast (MLBAM-id keyed); deprecate build_from_pybaseball (#1.5)"
```

---

## Task 4: Add park_id + pregame_prior_source to snapshots

**Files:**
- Modify: `C:/Users/johnny/Desktop/mlb_model/data/state_snapshot_builder.py`

- [ ] **Step 1: Read the current file's snapshot-row construction**

```bash
cd C:/Users/johnny/Desktop/mlb_model && grep -n "home_pitcher_id\|pregame_win_prob\|home_won_final" data/state_snapshot_builder.py
```

You should see a dict-literal assembly block (around lines 240–270) that builds each snapshot row with keys like `"home_pitcher_id": ...`, `"pregame_win_prob": ...`, `"home_won_final": ...`. This is where you add the two new fields.

- [ ] **Step 2: Add the import for `lookup_park_id` near the top of the file**

Find the existing imports block (after `import pandas as pd`). Add this line:

```python
from sports.mlb.parks import lookup_park_id
```

- [ ] **Step 3: Add `park_id` + `pregame_prior_source` to the snapshot row literal**

Locate the dict-literal that builds each snapshot row (it's the line that has `"home_pitcher_id": home_pitcher_id,`). Find the closing brace of that dict (right before the row is appended to a list). Insert these two new key-value pairs IMMEDIATELY BEFORE the closing brace:

```python
                "park_id": lookup_park_id(home_team),
                "pregame_prior_source": 1,   # historical rows always elo
```

(Indentation must match the surrounding `"home_pitcher_id": home_pitcher_id,` line — typically 16 spaces.)

If the snapshot dict appears in MULTIPLE places in the file (e.g. one for early-game and one for mid-game rows), apply the same insertion to each.

- [ ] **Step 4: Smoke test the import + a synthetic snapshot generation**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -c "
import data.state_snapshot_builder
from sports.mlb.parks import lookup_park_id
print('import OK')
print('LAA →', lookup_park_id('LAA'))
"
```
Expected: `import OK`, `LAA → ANA01`.

- [ ] **Step 5: Verify with a re-run on one season (optional, slow)**

This step is OPTIONAL — only run if you want to actually regenerate one season's snapshots to confirm the new columns appear. Otherwise commit and let Task 8 / operator's full retrain confirm it.

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m data.state_snapshot_builder --seasons 2025
# then:
python -c "
import pandas as pd
df = pd.read_parquet('data/features/snapshots_2025.parquet')
print('cols:', list(df.columns))
assert 'park_id' in df.columns, 'park_id missing'
assert 'pregame_prior_source' in df.columns, 'pregame_prior_source missing'
print('park_id non-default rate:', (df.park_id != 'unknown').mean())
"
```
Expected: park_id and pregame_prior_source in columns; non-default rate > 0.95 (should be 1.0 for all current franchises).

If you skip step 5, just confirm the import works in step 4.

- [ ] **Step 6: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/data/state_snapshot_builder.py && git commit -m "mlb_model: emit park_id + pregame_prior_source on snapshot rows (#1.5)"
```

---

## Task 5: Daily incremental pitcher quality refresh script

**Files:**
- Create: `C:/Users/johnny/Desktop/mlb_model/scripts/refresh_pitcher_quality_daily.py`

- [ ] **Step 1: Implement `scripts/refresh_pitcher_quality_daily.py`**

Exact content:

```python
"""
scripts/refresh_pitcher_quality_daily.py

Daily incremental refresh of pitcher_quality.parquet.

Strategy:
  1. Aggregate yesterday's Statcast pitches into per-(pitcher_id, game_pk) FIP rows
  2. Append those rows to the existing pitcher_quality history
  3. Re-run compute_pitcher_quality_pointtime over the combined history
  4. Write back atomically (.tmp → rename)

Idempotent: re-running on the same day overwrites with identical data (the
aggregator deduplicates by (pitcher_id, game_pk)).

If yesterday had no Statcast data (off-day, scrape lag), exits 0 with a no-op log.
"""
from __future__ import annotations
import logging
import os
from datetime import date, timedelta
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

PITCHER_QUALITY_PATH = Path("data/features/pitcher_quality.parquet")
STATCAST_DIR = Path("data/raw/statcast")


def _load_yesterdays_pitches(target_date: date) -> pd.DataFrame:
    """Load only the parquet that contains target_date (e.g. 2026_04.parquet)."""
    target_file = STATCAST_DIR / f"{target_date.year}_{target_date.month:02d}.parquet"
    if not target_file.exists():
        return pd.DataFrame()
    cols = ["pitcher", "game_pk", "game_date", "events"]
    df = pd.read_parquet(target_file, columns=cols)
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

    from data.foundation.statcast_pitcher_aggregator import aggregate_per_pitcher_per_game
    from data.foundation.pitcher_quality_builder import compute_pitcher_quality_pointtime

    new_starts = aggregate_per_pitcher_per_game(pitches)
    new_starts = new_starts[new_starts["fip"].notna() & (new_starts["ip"] >= 4.0)].copy()
    if new_starts.empty:
        print(f"No qualifying starts on {yesterday}.")
        return 0
    new_starts["pitcher_id"] = new_starts["pitcher_id"].astype(str)

    # Load existing pitcher_quality history if present (for combined re-compute,
    # we'd need the underlying *starts* not the rolled-up table; for this script
    # we just append yesterday's rolled-up rows).
    if PITCHER_QUALITY_PATH.exists():
        existing = pd.read_parquet(PITCHER_QUALITY_PATH)
    else:
        existing = pd.DataFrame()

    yesterday_pq = compute_pitcher_quality_pointtime(
        new_starts[["pitcher_id", "game_date", "ip", "fip", "season"]],
        snapshot_dates=[yesterday + timedelta(days=1)],   # quality "as of tomorrow"
    )
    if existing.empty:
        out = yesterday_pq
    else:
        out = pd.concat([existing, yesterday_pq], ignore_index=True)
        out = out.drop_duplicates(subset=["pitcher_id", "as_of_date"], keep="last")

    PITCHER_QUALITY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PITCHER_QUALITY_PATH.with_suffix(".parquet.tmp")
    out.to_parquet(tmp, index=False)
    os.replace(tmp, PITCHER_QUALITY_PATH)
    print(f"Refreshed pitcher_quality.parquet: +{len(yesterday_pq)} rows for {yesterday}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke test the import**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -c "import py_compile; py_compile.compile('scripts/refresh_pitcher_quality_daily.py', doraise=True); print('OK')"
```
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/scripts/refresh_pitcher_quality_daily.py && git commit -m "mlb_model: add daily incremental pitcher quality refresh script (#1.5)"
```

---

## Task 6: Extend integration test for new statcast path

**Files:**
- Modify: `C:/Users/johnny/Desktop/mlb_model/tests/integration/test_full_pipeline.py`

- [ ] **Step 1: Append a new test function to the existing file**

Open `tests/integration/test_full_pipeline.py` and APPEND this new test function at the bottom (after the existing `test_synthetic_pipeline_produces_parquets`):

```python
def test_statcast_path_produces_pitcher_quality(tmp_path, monkeypatch):
    """End-to-end: Statcast pitches → aggregate → pitcher_quality_pointtime."""
    monkeypatch.chdir(tmp_path)
    Path("data/features").mkdir(parents=True, exist_ok=True)

    from data.foundation.statcast_pitcher_aggregator import aggregate_per_pitcher_per_game
    from data.foundation.pitcher_quality_builder import compute_pitcher_quality_pointtime

    # 60 IP across 10 starts for one pitcher in 2024
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
    # 6 IP per start, FIP = (0+0-2*1)/6 + 3.2 = 2.867 → quality ~ 71.7 (lower than 100)
    assert pq.iloc[0]["sp_quality"] < 100.0
```

(Note: this assumes `from datetime import date, timedelta` and `import pandas as pd` are already imported at the top of the existing file. They are — verify before saving.)

- [ ] **Step 2: Run integration tests**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/integration/ -v
```
Expected: 3 PASSED (2 existing + 1 new).

- [ ] **Step 3: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/tests/integration/test_full_pipeline.py && git commit -m "mlb_model: extend integration tests with statcast pitcher path (#1.5)"
```

---

## Task 7: Create 3 daily scheduled triggers via `superpowers:schedule`

**No files — uses the skill directly.**

This task uses the `superpowers:schedule` skill to register 3 cron triggers in the operator's Claude Code account. Each trigger fires a fresh Claude Code agent on the schedule, which runs the specified script and reports back.

- [ ] **Step 1: Invoke the schedule skill to create `mlb-elo-daily`**

Use the `Skill` tool with skill name `schedule`. Provide arguments to create a new trigger with these properties:

- name: `mlb-elo-daily`
- cron: `0 11 * * *`
- prompt: `cd C:/Users/johnny/Desktop/mlb_model && python scripts/update_elo_daily.py. Report the last 5 lines of stdout. If exit code is non-zero, surface the error clearly.`

(Exact tool invocation will depend on the skill's interface. The skill may prompt you for additional fields like timezone or model — accept defaults: timezone UTC, model haiku.)

- [ ] **Step 2: Invoke the schedule skill to create `mlb-pitcher-quality-daily`**

- name: `mlb-pitcher-quality-daily`
- cron: `0 13 * * *`
- prompt: `cd C:/Users/johnny/Desktop/mlb_model && python scripts/refresh_pitcher_quality_daily.py. Report the last 5 lines of stdout. If exit code is non-zero, surface the error clearly.`

- [ ] **Step 3: Invoke the schedule skill to create `mlb-sharp-odds-daily`**

- name: `mlb-sharp-odds-daily`
- cron: `0 14 * * *`
- prompt: `cd C:/Users/johnny/Desktop/mlb_model && python scripts/update_sharp_odds_daily.py. Report the last 5 lines of stdout. If exit code is non-zero, surface the error clearly.`

- [ ] **Step 4: List existing triggers to confirm all 3 are registered**

Use the schedule skill's list capability (or `mcp__schedule__schedule_list` tool if available) and verify the 3 triggers appear with the expected cron expressions.

Report each trigger's ID for the operator's records.

- [ ] **Step 5: No commit needed (no file changes)**

---

## Task 8: Final smoke + verification

**Files:** none (validation only)

- [ ] **Step 1: Run all unit + integration tests**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/ -v
```
Expected: All tests pass (32+ tests after #1.5 additions: 26 from #1 + 4 parks + 4 statcast aggregator + 1 new integration test).

- [ ] **Step 2: Verify all imports clean**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -c "
import integration.recommendation_api
from data.foundation.pitcher_quality_builder import build_from_statcast, build_from_pybaseball
from data.foundation.statcast_pitcher_aggregator import aggregate_per_pitcher_per_game, aggregate_from_statcast_dir
from sports.mlb.parks import TEAM_TO_PARK, lookup_park_id, ALL_TEAMS
import scripts.refresh_pitcher_quality_daily as _
print('all imports OK')
print('TEAM_TO_PARK:', len(TEAM_TO_PARK), 'entries')
print('ALL_TEAMS:', len(ALL_TEAMS))
"
```
Expected: `all imports OK`, ~37 entries in TEAM_TO_PARK (30 + a few aliases), 30 in ALL_TEAMS.

- [ ] **Step 3: Verify the 3 cron triggers are registered**

Use the schedule skill to list triggers; confirm `mlb-elo-daily`, `mlb-pitcher-quality-daily`, `mlb-sharp-odds-daily` appear.

- [ ] **Step 4: Document the next manual step for the operator**

Print/report:

> **Operator next step:** Run `python -m data.state_snapshot_builder --seasons 2018 2019 2020 2021 2022 2023 2024 2025` to regenerate snapshots with park_id + pregame_prior_source columns. Then `python -m data.foundation.pitcher_quality_builder` to populate pitcher_quality.parquet from local Statcast (no network calls). Then `python scripts/retrain_after_features.py` for the audit-gated retrain. Inspect `artifacts/audit_report.json` — phase-1 features should now show non-zero ablation delta.

---

## What's NOT in this plan (intentionally)

- **Running the actual snapshot regeneration** — that's CPU-bound on 1.4M rows; operator's call to schedule it
- **Running the full retrain** — same as above; runbook step
- **Sub-projects #2 (batter quality), #3 (bullpen), #4 (weather)** — separate brainstorming → spec → plan cycles

---

## Spec coverage check

| Spec section | Implementation task |
|---|---|
| §1 Architecture / file map | Tasks 1–6 |
| §2 Snapshot schema additions | Task 4 |
| §3 Pitcher quality from Statcast | Tasks 2, 3 |
| §4 Daily cron triggers | Task 7 |
| §5 Error handling | Tasks 5 (atomic write, no-op exit), 1 (unknown park fallback) |
| §6 Testing — unit | Tasks 1, 2 |
| §6 Testing — integration | Task 6 |
| §6 Manual smoke after retrain | Task 8 step 4 |
