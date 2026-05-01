# MLB Model Signal Quality #4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 5 weather+extras features (wind_out_mph, temp_f, is_roof_closed, in_extras, ghost_runner_on_2nd). Feature count 34 → 39.

**Architecture:** Static 30-row `park_metadata.parquet` for orientation/roof. Open-Meteo archive API backfills weather per game_pk into `game_weather.parquet`. Extras features are pure-derived at snapshot+feature time. Audit ship via PROMOTE_MARGINAL (from #3 override).

**Tech Stack:** Python 3.11, pandas/pyarrow, urllib, Open-Meteo API (free, no key).

**Spec:** `docs/superpowers/specs/2026-04-20-mlb-model-signal-quality-4-design.md`

---

## File Map

### New
| Path | Responsibility |
|---|---|
| `data/foundation/park_metadata_builder.py` | Hand-coded 30-park table (lat/lon, orientation, roof flags) |
| `data/foundation/weather_fetcher.py` | Open-Meteo API wrapper (archive + forecast) |
| `data/foundation/weather_backfill.py` | Batch fetch historical weather per game_pk → game_weather.parquet |
| `sports/mlb/park_metadata_live.py` | `(park_id) → metadata` lookup |
| `sports/mlb/weather_live.py` | `(park_id, game_datetime) → WeatherSnapshot` lookup (calls forecast API) |
| `scripts/refresh_weather_daily.py` | Daily fetch today + yesterday's weather |
| `scripts/cron/run_refresh_weather_daily.bat` | Windows wrapper |
| `tests/test_park_metadata_builder.py` | Unit |
| `tests/test_weather_fetcher.py` | Unit (mocked HTTP) |
| `tests/test_park_metadata_live.py` | Unit |
| `tests/test_weather_live.py` | Unit (mocked HTTP) |

### Modified
| Path | Change |
|---|---|
| `data/state_snapshot_builder.py` | Emit `in_extras` + `ghost_runner_on_2nd` derived fields |
| `data/feature_store.py` | FEATURE_COLUMNS 34→39, enrichment block for weather + extras |
| `sports/mlb/winprob_inference.py` | `phase4_extras` param; 5 new features |
| `integration/recommendation_api.py` | Build phase4_extras, pass to inference, surface in reasons |
| `core/selfcheck.py` | `EXPECTED_FEATURE_COUNT = 39` |
| `models/audit_features.py` | `PHASE4_NEW_FEATURES` constant |
| `scripts/cron/install_scheduled_tasks.bat` | +1 task (7 total), update completion echo |
| `tests/integration/test_full_pipeline.py` | Extend with weather path |

---

## Task 1: Park metadata static table

**Files:**
- Create: `C:/Users/johnny/Desktop/mlb_model/data/foundation/park_metadata_builder.py`
- Create: `C:/Users/johnny/Desktop/mlb_model/tests/test_park_metadata_builder.py`

- [ ] **Step 1 (TDD): Write failing test**

```python
import pytest
from data.foundation.park_metadata_builder import (
    build_park_metadata,
    PARK_METADATA,
)

def test_all_30_current_parks_present():
    df = build_park_metadata()
    assert len(df) == 30

def test_coors_is_outdoor():
    df = build_park_metadata()
    coors = df[df.park_id == "DEN02"].iloc[0]
    assert coors.has_roof == 0
    assert coors.is_indoor == 0

def test_tropicana_is_indoor():
    df = build_park_metadata()
    tropicana = df[df.park_id == "STP01"].iloc[0]
    assert tropicana.has_roof == 1
    assert tropicana.is_indoor == 1

def test_chase_field_has_retractable_roof():
    df = build_park_metadata()
    chase = df[df.park_id == "PHO01"].iloc[0]
    assert chase.has_roof == 1
    assert chase.is_retractable == 1

def test_every_park_has_lat_lon_orientation():
    df = build_park_metadata()
    assert df["latitude"].notna().all()
    assert df["longitude"].notna().all()
    assert df["outfield_orientation_deg"].notna().all()
```

- [ ] **Step 2: Run test, confirm fails**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_park_metadata_builder.py -v
```

- [ ] **Step 3: Implement `data/foundation/park_metadata_builder.py`**

```python
"""
data/foundation/park_metadata_builder.py

Static 30-row table of MLB park metadata. Used for:
  - Weather fetching (needs lat/lon)
  - Wind projection onto outfield axis (needs orientation)
  - Indoor/roof gating (indoor games get neutral weather)

Orientations: compass bearing of home plate -> center field axis (degrees).
A wind blowing FROM that direction blows the ball OUT (positive wind_out).

Hand-coded from public stadium data. Update if a team relocates.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

OUTPUT_PATH = Path("data/features/park_metadata.parquet")

# (park_id, park_name, lat, lon, outfield_orientation_deg, has_roof, is_retractable, is_indoor)
PARK_METADATA = [
    ("BAL12", "Oriole Park at Camden Yards",  39.2838,  -76.6217,  37, 0, 0, 0),
    ("BOS07", "Fenway Park",                   42.3467,  -71.0972,  45, 0, 0, 0),
    ("NYC21", "Yankee Stadium",                40.8296,  -73.9262,  74, 0, 0, 0),
    ("STP01", "Tropicana Field",               27.7682,  -82.6534,  46, 1, 0, 1),
    ("TOR02", "Rogers Centre",                 43.6414,  -79.3894,   0, 1, 1, 0),
    ("CHI12", "Guaranteed Rate Field",         41.8300,  -87.6338,  40, 0, 0, 0),
    ("CLE08", "Progressive Field",             41.4958,  -81.6852,   0, 0, 0, 0),
    ("DET05", "Comerica Park",                 42.3390,  -83.0485, 150, 0, 0, 0),
    ("KAN06", "Kauffman Stadium",              39.0517,  -94.4803,  45, 0, 0, 0),
    ("MIN04", "Target Field",                  44.9817,  -93.2776,  90, 0, 0, 0),
    ("OAK01", "Oakland Coliseum",              37.7515, -122.2006,  60, 0, 0, 0),
    ("HOU03", "Minute Maid / Daikin Park",     29.7572,  -95.3550,  20, 1, 1, 0),
    ("ANA01", "Angel Stadium",                 33.8003, -117.8827,  45, 0, 0, 0),
    ("SEA03", "T-Mobile Park",                 47.5914, -122.3325,  45, 1, 1, 0),
    ("ARL02", "Globe Life Field",              32.7473,  -97.0817,   0, 1, 1, 0),
    ("ATL03", "Truist Park",                   33.8908,  -84.4678, 150, 0, 0, 0),
    ("MIA02", "loanDepot park",                25.7781,  -80.2197,  40, 1, 1, 0),
    ("NYC20", "Citi Field",                    40.7571,  -73.8458,   0, 0, 0, 0),
    ("PHI13", "Citizens Bank Park",            39.9061,  -75.1665,  15, 0, 0, 0),
    ("WAS11", "Nationals Park",                38.8729,  -77.0074,   0, 0, 0, 0),
    ("CHI11", "Wrigley Field",                 41.9484,  -87.6553,  30, 0, 0, 0),
    ("CIN09", "Great American Ball Park",      39.0975,  -84.5069, 100, 0, 0, 0),
    ("MIL06", "American Family Field",         43.0280,  -87.9712,  60, 1, 1, 0),
    ("PIT08", "PNC Park",                      40.4469,  -80.0057, 120, 0, 0, 0),
    ("STL10", "Busch Stadium",                 38.6226,  -90.1928,  60, 0, 0, 0),
    ("PHO01", "Chase Field",                   33.4453, -112.0667,  15, 1, 1, 0),
    ("DEN02", "Coors Field",                   39.7559, -104.9942,   0, 0, 0, 0),
    ("LOS03", "Dodger Stadium",                34.0739, -118.2400,  25, 0, 0, 0),
    ("SAN02", "Petco Park",                    32.7073, -117.1566,  30, 0, 0, 0),
    ("SFO03", "Oracle Park",                   37.7786, -122.3893,  90, 0, 0, 0),
]


def build_park_metadata() -> pd.DataFrame:
    return pd.DataFrame(PARK_METADATA, columns=[
        "park_id", "park_name", "latitude", "longitude",
        "outfield_orientation_deg", "has_roof", "is_retractable", "is_indoor",
    ])


def main() -> None:
    df = build_park_metadata()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests (5/5 PASSED)**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_park_metadata_builder.py -v
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/data/foundation/park_metadata_builder.py mlb_model/tests/test_park_metadata_builder.py && git commit -m "mlb_model: add static 30-park metadata (lat/lon, orientation, roof) (#4)"
```

---

## Task 2: Park metadata live lookup

**Files:**
- Create: `C:/Users/johnny/Desktop/mlb_model/sports/mlb/park_metadata_live.py`
- Create: `C:/Users/johnny/Desktop/mlb_model/tests/test_park_metadata_live.py`

- [ ] **Step 1 (TDD): Write failing test**

```python
import pandas as pd
import pytest
from sports.mlb.park_metadata_live import lookup_park_metadata, _set_test_table, ParkMetadata

@pytest.fixture(autouse=True)
def reset():
    yield
    _set_test_table(None)

def test_lookup_known_outdoor():
    tbl = pd.DataFrame([{
        "park_id": "DEN02", "park_name": "Coors", "latitude": 39.75, "longitude": -104.99,
        "outfield_orientation_deg": 0, "has_roof": 0, "is_retractable": 0, "is_indoor": 0,
    }])
    _set_test_table(tbl)
    m = lookup_park_metadata("DEN02")
    assert m.latitude == pytest.approx(39.75)
    assert m.is_indoor is False
    assert m.has_roof is False

def test_lookup_unknown_returns_indoor_neutral():
    _set_test_table(pd.DataFrame(columns=[
        "park_id", "park_name", "latitude", "longitude",
        "outfield_orientation_deg", "has_roof", "is_retractable", "is_indoor",
    ]))
    m = lookup_park_metadata("XXX")
    assert m.is_indoor is True   # safe default for unknowns
    assert m.has_roof is True
```

- [ ] **Step 2: Run, confirm fails**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_park_metadata_live.py -v
```

- [ ] **Step 3: Implement `sports/mlb/park_metadata_live.py`**

```python
"""sports/mlb/park_metadata_live.py — Live (park_id) -> park metadata lookup."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)
_TABLE: Optional[pd.DataFrame] = None
_TABLE_PATH = Path("data/features/park_metadata.parquet")


@dataclass
class ParkMetadata:
    park_id: str
    park_name: str
    latitude: float
    longitude: float
    outfield_orientation_deg: float
    has_roof: bool
    is_retractable: bool
    is_indoor: bool


def _load_table() -> pd.DataFrame:
    global _TABLE
    if _TABLE is None:
        if _TABLE_PATH.exists():
            _TABLE = pd.read_parquet(_TABLE_PATH)
        else:
            _TABLE = pd.DataFrame(columns=[
                "park_id", "park_name", "latitude", "longitude",
                "outfield_orientation_deg", "has_roof", "is_retractable", "is_indoor",
            ])
    return _TABLE


def _set_test_table(df: Optional[pd.DataFrame]) -> None:
    global _TABLE
    _TABLE = df


def lookup_park_metadata(park_id: str) -> ParkMetadata:
    """Return metadata for park_id. Unknown parks default to indoor neutral (safe)."""
    table = _load_table()
    rows = table[table["park_id"] == park_id]
    if rows.empty:
        logger.info("Unknown park_id=%s, defaulting to indoor neutral", park_id)
        return ParkMetadata(
            park_id=park_id, park_name="unknown",
            latitude=0.0, longitude=0.0, outfield_orientation_deg=0.0,
            has_roof=True, is_retractable=False, is_indoor=True,
        )
    r = rows.iloc[0]
    return ParkMetadata(
        park_id=str(r["park_id"]),
        park_name=str(r["park_name"]),
        latitude=float(r["latitude"]),
        longitude=float(r["longitude"]),
        outfield_orientation_deg=float(r["outfield_orientation_deg"]),
        has_roof=bool(r["has_roof"]),
        is_retractable=bool(r["is_retractable"]),
        is_indoor=bool(r["is_indoor"]),
    )
```

- [ ] **Step 4: Run tests (2/2 PASSED)**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_park_metadata_live.py -v
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/sports/mlb/park_metadata_live.py mlb_model/tests/test_park_metadata_live.py && git commit -m "mlb_model: add park metadata live lookup (#4)"
```

---

## Task 3: Weather fetcher (Open-Meteo wrapper)

**Files:**
- Create: `C:/Users/johnny/Desktop/mlb_model/data/foundation/weather_fetcher.py`
- Create: `C:/Users/johnny/Desktop/mlb_model/tests/test_weather_fetcher.py`

- [ ] **Step 1 (TDD): Write failing test**

```python
import pytest
from datetime import datetime, timezone
from data.foundation.weather_fetcher import (
    fetch_weather_at, parse_open_meteo_response, project_wind,
    WeatherSnapshot, WeatherError,
)

_MOCK_ARCHIVE = {
    "hourly": {
        "time": ["2024-07-15T18:00", "2024-07-15T19:00", "2024-07-15T20:00"],
        "temperature_2m": [75.0, 78.0, 80.0],
        "wind_speed_10m": [10.0, 12.0, 15.0],
        "wind_direction_10m": [180.0, 200.0, 210.0],
    }
}

def test_parse_picks_closest_hour():
    # Game at 19:30 UTC → closest hour is 20:00 (78° temp, 12 mph, 200° dir)
    snap = parse_open_meteo_response(_MOCK_ARCHIVE,
                                     target=datetime(2024, 7, 15, 19, 30, tzinfo=timezone.utc))
    # 19:30 is equidistant to 19:00 and 20:00; implementation may pick either. Test both.
    assert snap.temp_f in (78.0, 80.0)

def test_project_wind_blowing_out():
    # Wind blowing FROM north (0°) at park oriented to CF=0° (also N) → full tailwind OUT
    w = project_wind(wind_mph=10, wind_from_deg=0, outfield_orientation_deg=0)
    assert w == pytest.approx(10.0)

def test_project_wind_blowing_in():
    # Wind FROM south (180°) at park oriented to CF=0° (N) → headwind IN (negative)
    w = project_wind(wind_mph=10, wind_from_deg=180, outfield_orientation_deg=0)
    assert w == pytest.approx(-10.0)

def test_project_wind_crosswind():
    # Wind FROM east (90°) at park oriented to CF=0° (N) → crosswind (zero along axis)
    w = project_wind(wind_mph=10, wind_from_deg=90, outfield_orientation_deg=0)
    assert abs(w) < 0.1

def test_fetch_raises_on_http_error(monkeypatch):
    def boom(*a, **kw): raise OSError("network down")
    monkeypatch.setattr("data.foundation.weather_fetcher._http_get_json", boom)
    with pytest.raises(WeatherError):
        fetch_weather_at(latitude=40.0, longitude=-75.0,
                         target=datetime(2024, 7, 15, 19, 0, tzinfo=timezone.utc))

def test_fetch_returns_parsed(monkeypatch):
    monkeypatch.setattr("data.foundation.weather_fetcher._http_get_json", lambda url: _MOCK_ARCHIVE)
    snap = fetch_weather_at(latitude=40.0, longitude=-75.0,
                            target=datetime(2024, 7, 15, 19, 0, tzinfo=timezone.utc))
    assert snap.temp_f == 78.0
    assert snap.wind_mph == 12.0
    assert snap.wind_from_deg == 200.0
```

- [ ] **Step 2: Run, confirm fails**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_weather_fetcher.py -v
```

- [ ] **Step 3: Implement `data/foundation/weather_fetcher.py`**

```python
"""
data/foundation/weather_fetcher.py

Open-Meteo archive + forecast API wrapper.

Archive (historical):
  https://archive-api.open-meteo.com/v1/archive?latitude=...&longitude=...
  &start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
  &hourly=temperature_2m,wind_speed_10m,wind_direction_10m
  &temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=UTC

Forecast (today/future):
  https://api.open-meteo.com/v1/forecast?latitude=...&longitude=...
  &hourly=temperature_2m,wind_speed_10m,wind_direction_10m
  &temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=UTC

Free tier: 10k requests/day. No API key needed.
"""
from __future__ import annotations
import json
import logging
import math
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

ARCHIVE_BASE = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_BASE = "https://api.open-meteo.com/v1/forecast"


class WeatherError(Exception):
    pass


@dataclass
class WeatherSnapshot:
    temp_f: float
    wind_mph: float
    wind_from_deg: float    # compass bearing wind is blowing FROM


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "mlb_model/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def project_wind(wind_mph: float, wind_from_deg: float,
                 outfield_orientation_deg: float) -> float:
    """
    Project wind onto the park's outfield axis.

    Returns +mph if blowing OUT toward CF, -mph if blowing IN from CF.
    Clamped to ±30 mph.
    """
    # Angle between wind source and outfield orientation
    angle_deg = wind_from_deg - outfield_orientation_deg
    angle_rad = math.radians(angle_deg)
    projected = wind_mph * math.cos(angle_rad)
    return max(-30.0, min(30.0, projected))


def parse_open_meteo_response(data: dict, target: datetime) -> WeatherSnapshot:
    """Pick the hourly reading closest to target datetime."""
    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    temps = hourly.get("temperature_2m") or []
    winds = hourly.get("wind_speed_10m") or []
    dirs = hourly.get("wind_direction_10m") or []
    if not times:
        raise WeatherError("no hourly data in response")

    # Pick index closest to target
    target_utc = target.astimezone(timezone.utc).replace(tzinfo=None)
    best_idx = 0
    best_diff = abs((datetime.fromisoformat(times[0]) - target_utc).total_seconds())
    for i, t_str in enumerate(times[1:], start=1):
        diff = abs((datetime.fromisoformat(t_str) - target_utc).total_seconds())
        if diff < best_diff:
            best_diff = diff
            best_idx = i

    return WeatherSnapshot(
        temp_f=float(temps[best_idx]) if best_idx < len(temps) else 70.0,
        wind_mph=float(winds[best_idx]) if best_idx < len(winds) else 0.0,
        wind_from_deg=float(dirs[best_idx]) if best_idx < len(dirs) else 0.0,
    )


def fetch_weather_at(latitude: float, longitude: float, target: datetime,
                     use_archive: bool = True) -> WeatherSnapshot:
    """
    Fetch hourly weather closest to target datetime.

    use_archive: True for historical dates (>3 days old), False for today/future.
    """
    base = ARCHIVE_BASE if use_archive else FORECAST_BASE
    date_str = target.strftime("%Y-%m-%d")
    url = (
        f"{base}?latitude={latitude}&longitude={longitude}"
        f"&start_date={date_str}&end_date={date_str}"
        f"&hourly=temperature_2m,wind_speed_10m,wind_direction_10m"
        f"&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=UTC"
    )
    try:
        data = _http_get_json(url)
    except Exception as e:
        raise WeatherError(f"Open-Meteo fetch failed: {e}") from e
    return parse_open_meteo_response(data, target)
```

- [ ] **Step 4: Run tests (6/6 PASSED)**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_weather_fetcher.py -v
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/data/foundation/weather_fetcher.py mlb_model/tests/test_weather_fetcher.py && git commit -m "mlb_model: add Open-Meteo weather fetcher + wind projection (#4)"
```

---

## Task 4: Weather backfill (per game_pk)

**Files:**
- Create: `C:/Users/johnny/Desktop/mlb_model/data/foundation/weather_backfill.py`

- [ ] **Step 1: Implement**

```python
"""
data/foundation/weather_backfill.py

Batch fetch weather for every unique (game_pk, park_id, game_datetime) in snapshots.
Writes to data/features/game_weather.parquet.

Indoor/closed-roof games get neutral defaults (no API call).

Usage:
    python -m data.foundation.weather_backfill [--seasons 2018 2019 ...]
"""
from __future__ import annotations
import argparse
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

from data.foundation.weather_fetcher import (
    fetch_weather_at, project_wind, WeatherError, WeatherSnapshot,
)
from data.foundation.park_metadata_builder import build_park_metadata

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("data/features/game_weather.parquet")
SNAPSHOT_DIR = Path("data/features")
REQUEST_SLEEP_SEC = 0.3   # avoid rate limits; 10k/day = ~115/hr


def _collect_game_dates(seasons: list[int] | None = None) -> pd.DataFrame:
    """Pull unique (game_id, park_id, date) rows from snapshot parquets."""
    parquets = sorted(SNAPSHOT_DIR.glob("snapshots_*.parquet"))
    frames = []
    for p in parquets:
        if seasons is not None:
            year = int(p.stem.split("_")[-1])
            if year not in seasons:
                continue
        df = pd.read_parquet(p, columns=["game_id", "park_id", "date"])
        frames.append(df.drop_duplicates(subset=["game_id"]))
    if not frames:
        return pd.DataFrame(columns=["game_id", "park_id", "date"])
    games = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["game_id"])
    return games


def backfill(seasons: list[int] | None = None) -> pd.DataFrame:
    parks = build_park_metadata().set_index("park_id")
    games = _collect_game_dates(seasons)
    logger.info("Backfilling weather for %d unique games", len(games))

    rows = []
    for i, g in games.iterrows():
        park_id = str(g["park_id"])
        if park_id not in parks.index:
            logger.info("Unknown park_id=%s, skipping (neutral weather)", park_id)
            rows.append({
                "game_id": str(g["game_id"]), "park_id": park_id,
                "temp_f": 70.0, "wind_mph": 0.0, "wind_from_deg": 0.0,
                "wind_out_mph": 0.0, "is_roof_closed": 1,
            })
            continue
        meta = parks.loc[park_id]
        if int(meta["is_indoor"]) == 1:
            # Always-indoor: neutral weather, roof closed
            rows.append({
                "game_id": str(g["game_id"]), "park_id": park_id,
                "temp_f": 70.0, "wind_mph": 0.0, "wind_from_deg": 0.0,
                "wind_out_mph": 0.0, "is_roof_closed": 1,
            })
            continue

        # Fetch weather for game date at 7pm local (approximate game time)
        try:
            date_obj = pd.to_datetime(str(g["date"])).to_pydatetime().replace(
                hour=19, minute=0, tzinfo=timezone.utc)
        except Exception:
            continue
        try:
            snap = fetch_weather_at(float(meta["latitude"]), float(meta["longitude"]),
                                    date_obj, use_archive=True)
        except WeatherError as e:
            logger.warning("weather fetch failed for %s on %s: %s",
                           park_id, g["date"], e)
            continue

        wind_out = project_wind(snap.wind_mph, snap.wind_from_deg,
                                float(meta["outfield_orientation_deg"]))
        # Retractable parks: assume open unless weather extreme (simplification;
        # MLB doesn't publish roof-state history). Set is_roof_closed=0 for outdoor
        # with retractable, relies on temp to drive HR effect.
        is_closed = 0
        rows.append({
            "game_id": str(g["game_id"]), "park_id": park_id,
            "temp_f": snap.temp_f, "wind_mph": snap.wind_mph,
            "wind_from_deg": snap.wind_from_deg,
            "wind_out_mph": wind_out, "is_roof_closed": is_closed,
        })
        time.sleep(REQUEST_SLEEP_SEC)
        if (i + 1) % 200 == 0:
            logger.info("  ...%d/%d games fetched", i + 1, len(games))

    return pd.DataFrame(rows)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Backfill historical weather per game_pk")
    parser.add_argument("--seasons", nargs="+", type=int, default=None)
    args = parser.parse_args()

    df = backfill(args.seasons)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test imports**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -c "from data.foundation.weather_backfill import backfill, _collect_game_dates; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/data/foundation/weather_backfill.py && git commit -m "mlb_model: add weather backfill per game_pk (#4)"
```

---

## Task 5: Weather live lookup

**Files:**
- Create: `C:/Users/johnny/Desktop/mlb_model/sports/mlb/weather_live.py`
- Create: `C:/Users/johnny/Desktop/mlb_model/tests/test_weather_live.py`

- [ ] **Step 1 (TDD): Write failing test**

```python
import pandas as pd
import pytest
from datetime import datetime, timezone
from sports.mlb.weather_live import (
    lookup_weather_for_game, _set_test_table, WeatherRow,
)

@pytest.fixture(autouse=True)
def reset():
    yield
    _set_test_table(None)

def test_lookup_known_game_returns_cached():
    tbl = pd.DataFrame([{
        "game_id": "g1", "park_id": "DEN02", "temp_f": 82.0,
        "wind_mph": 8.0, "wind_from_deg": 180.0,
        "wind_out_mph": -8.0, "is_roof_closed": 0,
    }])
    _set_test_table(tbl)
    w = lookup_weather_for_game("g1")
    assert w.temp_f == pytest.approx(82.0)
    assert w.wind_out_mph == pytest.approx(-8.0)
    assert w.is_roof_closed is False

def test_lookup_unknown_game_returns_neutral():
    _set_test_table(pd.DataFrame(columns=[
        "game_id", "park_id", "temp_f", "wind_mph", "wind_from_deg",
        "wind_out_mph", "is_roof_closed",
    ]))
    w = lookup_weather_for_game("unknown")
    assert w.temp_f == 70.0
    assert w.wind_out_mph == 0.0
    assert w.is_roof_closed is True
```

- [ ] **Step 2: Run, confirm fails**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_weather_live.py -v
```

- [ ] **Step 3: Implement `sports/mlb/weather_live.py`**

```python
"""sports/mlb/weather_live.py — Live (game_id) -> weather row lookup."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)
_TABLE: Optional[pd.DataFrame] = None
_TABLE_PATH = Path("data/features/game_weather.parquet")


@dataclass
class WeatherRow:
    temp_f: float
    wind_out_mph: float
    is_roof_closed: bool


def _load_table() -> pd.DataFrame:
    global _TABLE
    if _TABLE is None:
        if _TABLE_PATH.exists():
            _TABLE = pd.read_parquet(_TABLE_PATH)
        else:
            _TABLE = pd.DataFrame(columns=[
                "game_id", "park_id", "temp_f", "wind_mph", "wind_from_deg",
                "wind_out_mph", "is_roof_closed",
            ])
    return _TABLE


def _set_test_table(df: Optional[pd.DataFrame]) -> None:
    global _TABLE
    _TABLE = df


def lookup_weather_for_game(game_id: str) -> WeatherRow:
    """Return weather for a given game_id. Neutral defaults if missing."""
    table = _load_table()
    if table.empty:
        return WeatherRow(temp_f=70.0, wind_out_mph=0.0, is_roof_closed=True)
    rows = table[table["game_id"] == str(game_id)]
    if rows.empty:
        return WeatherRow(temp_f=70.0, wind_out_mph=0.0, is_roof_closed=True)
    r = rows.iloc[0]
    return WeatherRow(
        temp_f=float(r["temp_f"]),
        wind_out_mph=float(r["wind_out_mph"]),
        is_roof_closed=bool(int(r["is_roof_closed"])),
    )
```

- [ ] **Step 4: Run tests (2/2 PASSED)**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_weather_live.py -v
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/sports/mlb/weather_live.py mlb_model/tests/test_weather_live.py && git commit -m "mlb_model: add weather live lookup (#4)"
```

---

## Task 6: Snapshot builder — in_extras + ghost_runner

**Files:**
- Modify: `C:/Users/johnny/Desktop/mlb_model/data/state_snapshot_builder.py`

- [ ] **Step 1: Find the snapshot dict literal location**

```bash
cd C:/Users/johnny/Desktop/mlb_model && grep -n "pregame_prior_source\|home_won_final" data/state_snapshot_builder.py
```

Locate the dict-literal line with `"pregame_prior_source": 1,`.

- [ ] **Step 2: Insert 2 new keys before `"home_won_final"`**

Find this exact block in the snapshot dict literal:

```python
                "current_lineup_position": (
```

Scroll to the end of the `current_lineup_position` assignment (the `else 0),` line). Then find the next line `"home_won_final": home_won,`.

Use the Edit tool to insert BEFORE `"home_won_final":`:

```python
                "in_extras": 1 if inning > 9 else 0,
                "ghost_runner_on_2nd": 1 if (inning > 9 and season >= 2020 and outs == 0) else 0,
```

(Indentation: 16 spaces.)

- [ ] **Step 3: Smoke test import**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -c "import data.state_snapshot_builder; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/data/state_snapshot_builder.py && git commit -m "mlb_model: emit in_extras + ghost_runner flags on snapshot rows (#4)"
```

---

## Task 7: Feature store enrichment (34 → 39)

**Files:**
- Modify: `C:/Users/johnny/Desktop/mlb_model/data/feature_store.py`

- [ ] **Step 1: Extend FEATURE_COLUMNS**

Find the existing line (from #3):

```python
    "leverage_index",
]
```

REPLACE with:

```python
    "leverage_index",

    # ── PHASE-4 weather + extras (added 2026-04-20) ──────────────────────────
    "wind_out_mph",
    "temp_f",
    "is_roof_closed",
    "in_extras",
    "ghost_runner_on_2nd",
]
```

- [ ] **Step 2: Forward new snapshot ID cols in engineer_features**

Find the block that forwards ID cols:

```python
    for id_col in [
        "home_pitcher_id", "away_pitcher_id",
        "batter_id", "batter_stand",
        "home_pitcher_p_throws", "away_pitcher_p_throws",
        "home_lineup_ids", "away_lineup_ids", "current_lineup_position",
        "park_id", "pregame_prior_source",
    ]:
        if id_col in df.columns:
            out[id_col] = df[id_col]
```

REPLACE with (add in_extras + ghost_runner_on_2nd):

```python
    for id_col in [
        "home_pitcher_id", "away_pitcher_id",
        "batter_id", "batter_stand",
        "home_pitcher_p_throws", "away_pitcher_p_throws",
        "home_lineup_ids", "away_lineup_ids", "current_lineup_position",
        "park_id", "pregame_prior_source",
        "in_extras", "ghost_runner_on_2nd",
    ]:
        if id_col in df.columns:
            out[id_col] = df[id_col]
```

- [ ] **Step 3: Extend enrichment with phase-4 block**

Find the final `return out` at the end of `enrich_with_phase1_features`. INSERT this block IMMEDIATELY BEFORE it:

```python
    # ── Phase-4: weather + extras ────────────────────────────────────────────
    gw_path = FEATURE_DIR / "game_weather.parquet"
    if gw_path.exists() and "game_id" in out.columns:
        gw = pd.read_parquet(gw_path)
        gw_lookup = {str(r["game_id"]): (float(r["temp_f"]), float(r["wind_out_mph"]),
                                         int(r["is_roof_closed"]))
                     for _, r in gw.iterrows()}
        def _get(g):
            v = gw_lookup.get(str(g))
            return v if v is not None else (70.0, 0.0, 1)
        weather_vals = [_get(g) for g in out["game_id"]]
        out["temp_f"] = [v[0] for v in weather_vals]
        out["wind_out_mph"] = [v[1] for v in weather_vals]
        out["is_roof_closed"] = [float(v[2]) for v in weather_vals]
    else:
        out["temp_f"] = 70.0
        out["wind_out_mph"] = 0.0
        out["is_roof_closed"] = 1.0

    # Extras features (pure derived — no parquet needed)
    if "in_extras" in out.columns:
        out["in_extras"] = out["in_extras"].astype(float)
    else:
        out["in_extras"] = (out["inning"] > 9).astype(float)
    if "ghost_runner_on_2nd" in out.columns:
        out["ghost_runner_on_2nd"] = out["ghost_runner_on_2nd"].astype(float)
    else:
        out["ghost_runner_on_2nd"] = (
            (out["inning"] > 9) & (out["season"] >= 2020) & (out["outs"] == 0)
        ).astype(float)

```

- [ ] **Step 4: Extend NaN guard exclusion list**

Find the existing base_cols exclusion list and add phase-4 features:

```python
        # phase-3
        "home_reliever_quality", "away_reliever_quality",
        "home_bullpen_avg_quality", "away_bullpen_avg_quality",
        "leverage_index",
    )]
```

REPLACE with:

```python
        # phase-3
        "home_reliever_quality", "away_reliever_quality",
        "home_bullpen_avg_quality", "away_bullpen_avg_quality",
        "leverage_index",
        # phase-4
        "wind_out_mph", "temp_f", "is_roof_closed",
        "in_extras", "ghost_runner_on_2nd",
    )]
```

- [ ] **Step 5: Smoke test**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -c "
from data.feature_store import FEATURE_COLUMNS, enrich_with_phase1_features
import pandas as pd
print('count:', len(FEATURE_COLUMNS))
assert len(FEATURE_COLUMNS) == 39
synthetic = pd.DataFrame({
    'pregame_logit': [0.0], 'score_diff': [0], 'late_game': [0.5],
    'half': [0], 'inning': [1], 'outs': [0], 'season': [2024],
})
out = enrich_with_phase1_features(synthetic)
for col in ['wind_out_mph', 'temp_f', 'is_roof_closed', 'in_extras', 'ghost_runner_on_2nd']:
    assert col in out.columns, f'missing {col}'
print('all 5 phase-4 columns present')
print('  temp_f:', float(out['temp_f'].iloc[0]))
print('  is_roof_closed:', float(out['is_roof_closed'].iloc[0]))
print('  in_extras:', float(out['in_extras'].iloc[0]))
"
```
Expected: count: 39, all 5 cols present, temp_f=70.0, is_roof_closed=1.0, in_extras=0.0.

- [ ] **Step 6: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/data/feature_store.py && git commit -m "mlb_model: extend feature_store with 5 phase-4 weather+extras cols (#4)"
```

---

## Task 8: Inference path (34 → 39)

**Files:**
- Modify: `C:/Users/johnny/Desktop/mlb_model/sports/mlb/winprob_inference.py`
- Modify: `C:/Users/johnny/Desktop/mlb_model/tests/test_winprob_inference.py`

- [ ] **Step 1: Add `_PHASE4_FEATURE_NAMES`**

Find `_PHASE3_FEATURE_NAMES = (...)`. INSERT below:

```python
_PHASE4_FEATURE_NAMES = (
    "wind_out_mph", "temp_f", "is_roof_closed",
    "in_extras", "ghost_runner_on_2nd",
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
    phase3_extras: dict | None = None,
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
    phase4_extras: dict | None = None,
) -> tuple[np.ndarray, dict[str, float], float]:
```

- [ ] **Step 3: Add phase-4 features block**

Find the existing phase-3 block ending with:

```python
    feat["leverage_index"] = float(p3.get("leverage_index", 1.0))
```

INSERT immediately AFTER:

```python
    # Phase-4 weather + extras
    p4 = phase4_extras or {}
    feat["wind_out_mph"] = float(p4.get("wind_out_mph", 0.0))
    feat["temp_f"] = float(p4.get("temp_f", 70.0))
    feat["is_roof_closed"] = float(p4.get("is_roof_closed", 1.0))
    feat["in_extras"] = 1.0 if float(snapshot.inning) > 9 else 0.0
    feat["ghost_runner_on_2nd"] = float(p4.get("ghost_runner_on_2nd", 0.0))
```

- [ ] **Step 4: Update `infer` and `infer_for_team` signatures**

Update `infer`:

```python
def infer(snapshot, pregame_win_prob: float = 0.54,
          phase1_extras: dict | None = None,
          phase2_extras: dict | None = None,
          phase3_extras: dict | None = None,
          phase4_extras: dict | None = None) -> InferenceResult:
    if _model is None or _calibrator is None:
        raise RuntimeError("Model artifacts not loaded.")
    X, feat_dict, quality = _build_feature_vector(snapshot, pregame_win_prob,
                                                   phase1_extras, phase2_extras,
                                                   phase3_extras, phase4_extras)
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

Update `infer_for_team`:

```python
def infer_for_team(snapshot, tracked_team, pregame_win_prob_home: float = 0.54,
                   phase1_extras: dict | None = None,
                   phase2_extras: dict | None = None,
                   phase3_extras: dict | None = None,
                   phase4_extras: dict | None = None):
    from sports.mlb.team_normalizer import normalize
    result = infer(snapshot, pregame_win_prob_home,
                   phase1_extras, phase2_extras, phase3_extras, phase4_extras)
    tracked = normalize(tracked_team)
    p_tracked = result.p_home if tracked == snapshot.home_team else result.p_away
    return round(p_tracked, 6), result
```

- [ ] **Step 5: Append tests**

APPEND to `tests/test_winprob_inference.py`:

```python


def test_phase4_feature_names_count():
    from sports.mlb.winprob_inference import _PHASE4_FEATURE_NAMES
    assert len(_PHASE4_FEATURE_NAMES) == 5


def test_build_vector_with_phase4_extras():
    from sports.mlb import winprob_inference as wi
    wi._feature_columns = [
        "pregame_logit","score_diff","abs_score_diff","tied","inning","half","outs",
        "game_progress","late_game","base_state","base_state_value",
        "score_diff_x_late","base_value_x_late","tied_x_late",
        "home_pitch_count_norm","home_tto","home_is_bullpen",
        "away_pitch_count_norm","away_tto","away_is_bullpen",
        "elo_diff_norm","late_tie_bottom",
        # phase-1 (pruned): 6 cols
        "home_sp_quality","away_sp_quality","home_sp_recent_form","away_sp_recent_form",
        "sp_quality_diff","park_run_factor",
        # phase-2 (pruned): 1 col
        "lineup_avg_xwoba",
        # phase-3: 5 cols
        "home_reliever_quality","away_reliever_quality",
        "home_bullpen_avg_quality","away_bullpen_avg_quality","leverage_index",
        # phase-4: 5 cols
        "wind_out_mph","temp_f","is_roof_closed","in_extras","ghost_runner_on_2nd",
    ]
    snap = SimpleNamespace(
        score_diff=0, inning=11, inning_half=1, outs=0, outs_elapsed=60,
        base_state=0, home_pitch_count=0, away_pitch_count=0,
        home_tto=1.0, away_tto=1.0, home_is_bullpen=True, away_is_bullpen=True,
    )
    p1 = {"home_sp_quality": 100, "away_sp_quality": 100,
          "home_sp_recent_form": 0, "away_sp_recent_form": 0,
          "park_run_factor": 1.0, "pregame_prior_source": 0,
          "home_sp_imputed": False, "away_sp_imputed": False}
    p2 = {"lineup_avg_xwoba": 100,
          "current_batter_imputed": False}
    p3 = {"home_reliever_quality": 100, "away_reliever_quality": 100,
          "home_bullpen_avg_quality": 100, "away_bullpen_avg_quality": 100,
          "leverage_index": 2.0}
    p4 = {"wind_out_mph": 12, "temp_f": 85, "is_roof_closed": 0,
          "ghost_runner_on_2nd": 1}
    X, feat, q = wi._build_feature_vector(snap, 0.55, p1, p2, p3, p4)
    assert X.shape == (1, 39)
    assert feat["wind_out_mph"] == 12
    assert feat["temp_f"] == 85
    assert feat["in_extras"] == 1.0   # inning=11 > 9
    assert feat["ghost_runner_on_2nd"] == 1
```

- [ ] **Step 6: Run tests**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/test_winprob_inference.py -v
```
Expected: 9 PASSED (7 existing + 2 new).

- [ ] **Step 7: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/sports/mlb/winprob_inference.py mlb_model/tests/test_winprob_inference.py && git commit -m "mlb_model: extend inference vector to 39 cols (phase-4) (#4)"
```

---

## Task 9: Wire phase-4 into recommendation_api

**Files:**
- Modify: `C:/Users/johnny/Desktop/mlb_model/integration/recommendation_api.py`

- [ ] **Step 1: Add imports**

Find:

```python
    from sports.mlb.leverage_index_live import lookup_leverage_index
```

REPLACE with:

```python
    from sports.mlb.leverage_index_live import lookup_leverage_index
    from sports.mlb.weather_live import lookup_weather_for_game
```

- [ ] **Step 2: Build phase4_extras after phase3**

Find the existing `phase3_extras = {...}` block (ends with `"leverage_index": lookup_leverage_index(...)` inside the dict, then closing `}`).

IMMEDIATELY AFTER the closing `}` of phase3_extras, INSERT:

```python

    # Phase-4: weather + extras
    w = lookup_weather_for_game(str(getattr(snap, "game_id", "") or getattr(snap, "game_pk", "")))
    phase4_extras = {
        "wind_out_mph": w.wind_out_mph,
        "temp_f": w.temp_f,
        "is_roof_closed": 1 if w.is_roof_closed else 0,
        "ghost_runner_on_2nd": 1 if (snap.inning > 9 and _gd.year >= 2020 and snap.outs == 0) else 0,
    }
```

- [ ] **Step 3: Update infer_for_team call**

Find:

```python
        p_tracked, infer_result = infer_for_team(snap, tracked_team, pregame_prob, phase1_extras, phase2_extras, phase3_extras)
```

REPLACE with:

```python
        p_tracked, infer_result = infer_for_team(snap, tracked_team, pregame_prob, phase1_extras, phase2_extras, phase3_extras, phase4_extras)
```

- [ ] **Step 4: Surface phase-4 in reasons**

Find the existing phase-3 reasons line:

```python
    reasons.append(f"pen: h={hrq:.0f} a={arq:.0f} | LI={li:.1f}")
```

APPEND IMMEDIATELY AFTER:

```python

    # Phase-4 weather + extras
    wm = feat.get("wind_out_mph", 0.0)
    tf = feat.get("temp_f", 70.0)
    roof = "closed" if feat.get("is_roof_closed", 1) else "open"
    extras_flag = "EXTRAS" if feat.get("in_extras", 0) else ""
    gr = "ghost" if feat.get("ghost_runner_on_2nd", 0) else ""
    reasons.append(f"weather: wind={wm:+.0f}mph temp={tf:.0f}F roof={roof} {extras_flag} {gr}".rstrip())
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
cd C:/Users/johnny/Desktop && git add mlb_model/integration/recommendation_api.py && git commit -m "mlb_model: wire phase-4 weather+extras into live recommendations (#4)"
```

---

## Task 10: Selfcheck + Audit constants

**Files:**
- Modify: `C:/Users/johnny/Desktop/mlb_model/core/selfcheck.py`
- Modify: `C:/Users/johnny/Desktop/mlb_model/models/audit_features.py`

- [ ] **Step 1: Bump selfcheck**

Find:

```python
EXPECTED_FEATURE_COUNT = 34
```

REPLACE with:

```python
EXPECTED_FEATURE_COUNT = 39
```

- [ ] **Step 2: Add PHASE4_NEW_FEATURES**

Find `PHASE3_NEW_FEATURES = [...]`. INSERT immediately after:

```python

PHASE4_NEW_FEATURES = [
    "wind_out_mph",
    "temp_f",
    "is_roof_closed",
    "in_extras",
    "ghost_runner_on_2nd",
]
```

- [ ] **Step 3: Update retrain orchestrator to include phase-4**

Find in `scripts/retrain_after_features.py`:

```python
    from models.audit_features import (
        write_audit_report, PHASE1_NEW_FEATURES, PHASE2_NEW_FEATURES, PHASE3_NEW_FEATURES
    )
    ...
    all_new_features = PHASE1_NEW_FEATURES + PHASE2_NEW_FEATURES + PHASE3_NEW_FEATURES
```

REPLACE with:

```python
    from models.audit_features import (
        write_audit_report, PHASE1_NEW_FEATURES, PHASE2_NEW_FEATURES,
        PHASE3_NEW_FEATURES, PHASE4_NEW_FEATURES,
    )
```

And:

```python
    all_new_features = PHASE1_NEW_FEATURES + PHASE2_NEW_FEATURES + PHASE3_NEW_FEATURES + PHASE4_NEW_FEATURES
```

- [ ] **Step 4: Smoke test**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -c "
from core.selfcheck import EXPECTED_FEATURE_COUNT
from models.audit_features import PHASE4_NEW_FEATURES
assert EXPECTED_FEATURE_COUNT == 39
assert len(PHASE4_NEW_FEATURES) == 5
print('T4-10 OK')
"
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/core/selfcheck.py mlb_model/models/audit_features.py mlb_model/scripts/retrain_after_features.py && git commit -m "mlb_model: bump EXPECTED_FEATURE_COUNT to 39 + add PHASE4_NEW_FEATURES (#4)"
```

---

## Task 11: Daily refresh + cron

**Files:**
- Create: `C:/Users/johnny/Desktop/mlb_model/scripts/refresh_weather_daily.py`
- Create: `C:/Users/johnny/Desktop/mlb_model/scripts/cron/run_refresh_weather_daily.bat`
- Modify: `C:/Users/johnny/Desktop/mlb_model/scripts/cron/install_scheduled_tasks.bat`

- [ ] **Step 1: Implement `scripts/refresh_weather_daily.py`**

```python
"""
scripts/refresh_weather_daily.py — Daily weather refresh.

Fetches forecast weather for today's MLB games and appends to game_weather.parquet.
Also backfills yesterday's games (in case they weren't fetched).
"""
from __future__ import annotations
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logger = logging.getLogger(__name__)

WEATHER_PATH = Path("data/features/game_weather.parquet")


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    from data.foundation.weather_backfill import backfill

    current_year = date.today().year
    df = backfill(seasons=[current_year])
    if df.empty:
        print("No games found to fetch weather for.")
        return 0

    existing = pd.read_parquet(WEATHER_PATH) if WEATHER_PATH.exists() else pd.DataFrame()
    if existing.empty:
        out = df
    else:
        combined = pd.concat([existing, df], ignore_index=True)
        out = combined.drop_duplicates(subset=["game_id"], keep="last")

    WEATHER_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = WEATHER_PATH.with_suffix(".parquet.tmp")
    out.to_parquet(tmp, index=False)
    os.replace(tmp, WEATHER_PATH)
    print(f"Refreshed game_weather.parquet: total rows = {len(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Implement `scripts/cron/run_refresh_weather_daily.bat`**

```
@echo off
REM Daily weather refresh — Windows scheduled task `mlb-weather-daily`
cd /d "C:\Users\johnny\Desktop\mlb_model"
"C:\Users\johnny\AppData\Local\Python\pythoncore-3.14-64\python.exe" scripts\refresh_weather_daily.py >> logs\cron.log 2>&1
exit /b %ERRORLEVEL%
```

- [ ] **Step 3: Update `install_scheduled_tasks.bat`**

Find this exact block:

```
echo Installing mlb-bullpen-quality-daily (08:45 daily)...
schtasks /Create /SC DAILY /TN mlb-bullpen-quality-daily /TR "C:\Users\johnny\Desktop\mlb_model\scripts\cron\run_refresh_bullpen_quality_daily.bat" /ST 08:45 /F
if errorlevel 1 goto :err
```

REPLACE with (inserts weather block AFTER bullpen):

```
echo Installing mlb-bullpen-quality-daily (08:45 daily)...
schtasks /Create /SC DAILY /TN mlb-bullpen-quality-daily /TR "C:\Users\johnny\Desktop\mlb_model\scripts\cron\run_refresh_bullpen_quality_daily.bat" /ST 08:45 /F
if errorlevel 1 goto :err

echo Installing mlb-weather-daily (09:15 daily)...
schtasks /Create /SC DAILY /TN mlb-weather-daily /TR "C:\Users\johnny\Desktop\mlb_model\scripts\cron\run_refresh_weather_daily.bat" /ST 09:15 /F
if errorlevel 1 goto :err
```

Also find and replace the completion echo:

```
echo All 6 tasks installed. Verify with: schtasks /Query /TN mlb-elo-daily
```

REPLACE with:

```
echo All 7 tasks installed. Verify with: schtasks /Query /TN mlb-elo-daily
```

- [ ] **Step 4: Smoke test**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -c "import py_compile; py_compile.compile('scripts/refresh_weather_daily.py', doraise=True); print('OK')"
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/johnny/Desktop && git add mlb_model/scripts/refresh_weather_daily.py mlb_model/scripts/cron/run_refresh_weather_daily.bat mlb_model/scripts/cron/install_scheduled_tasks.bat && git commit -m "mlb_model: add daily weather refresh + cron wrapper (#4)"
```

---

## Task 12: Final smoke + verification

**Files:** none

- [ ] **Step 1: Run all tests**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -m pytest tests/ -v 2>&1 | tail -20
```
Expected: ~85+ PASSED (75 from prior + weather/park_metadata tests).

- [ ] **Step 2: Count consistency**

```bash
cd C:/Users/johnny/Desktop/mlb_model && python -c "
from data.feature_store import FEATURE_COLUMNS
from sports.mlb.winprob_inference import _PHASE4_FEATURE_NAMES
from models.audit_features import PHASE1_NEW_FEATURES, PHASE2_NEW_FEATURES, PHASE3_NEW_FEATURES, PHASE4_NEW_FEATURES
from core.selfcheck import EXPECTED_FEATURE_COUNT

print('FEATURE_COLUMNS:', len(FEATURE_COLUMNS))
print('PHASE1+2+3+4:', len(PHASE1_NEW_FEATURES)+len(PHASE2_NEW_FEATURES)+len(PHASE3_NEW_FEATURES)+len(PHASE4_NEW_FEATURES))
print('EXPECTED:', EXPECTED_FEATURE_COUNT)
assert len(FEATURE_COLUMNS) == 39
assert EXPECTED_FEATURE_COUNT == 39
print('consistent: 22 + 6 + 1 + 5 + 5 = 39')
"
```

- [ ] **Step 3: Document operator follow-up**

Print:

> **Operator next steps:**
> 1. Bootstrap: `python -m data.foundation.park_metadata_builder && python -m data.foundation.weather_backfill --seasons 2018 2019 2020 2021 2022 2023 2024 2025` (~2-3 hrs for weather API at 0.3s/call × ~19K games)
> 2. Regenerate snapshots once (for `in_extras` + `ghost_runner_on_2nd` cols): `python -m data.state_snapshot_builder --seasons 2018 2019 2020 2021 2022 2023 2024 2025`
> 3. Reinstall scheduled tasks (now 7): `scripts\cron\install_scheduled_tasks.bat`
> 4. Retrain: `python scripts\retrain_after_features.py`
> 5. Inspect `artifacts\audit_report.json` — expect PROMOTE_MARGINAL or REJECT.

---

## What's NOT in this plan (intentionally)

- **Umpire quality** — separate sub-project if desired
- **Precipitation / rain-delay detection** — weather doesn't include precipitation yet
- **Separate extras-inning sub-model** — spec notes small N; flags are sufficient

## Spec coverage check

| Spec section | Task |
|---|---|
| §1 Architecture / file map | Tasks 1-11 |
| §2 Features (34→39) | Tasks 7, 8 |
| §3 Park metadata schema | Task 1 |
| §4 Weather data (Open-Meteo) | Task 3 |
| §5 Extras-inning features | Task 6 (snapshot), Task 7 (enrichment) |
| §6 Audit gates | Task 10 |
| §7 Error handling | Tasks 2, 5 (neutral defaults), 4 (skip failed fetches) |
| §9 Cron | Task 11 |
