# MLB Model Signal Quality — Sub-Project #4 Design

**Date:** 2026-04-20
**Status:** Approved (auto-mode)
**Scope:** Weather + extras-inning features
**Parent:** #1, #1.5, #2, #3 shipped 2026-04-19/20 (34 features deployed via PROMOTE_MARGINAL)

## Locked decisions

| Question | Choice |
|---|---|
| Weather source | Open-Meteo (free, no API key, 40yr archive + forecast) |
| Weather features | 3: `wind_out_mph` (projected to outfield axis), `temp_f`, `is_roof_closed` |
| Extras approach | Feature flags (not separate sub-model — small N) |
| Extras features | 2: `in_extras`, `ghost_runner_on_2nd` |
| Park metadata | Static 30-row table: orientation, has_roof, retractable, indoor |

## §1 Architecture / file map

```
data/foundation/
├── weather_fetcher.py              ← NEW: open-meteo archive API wrapper
├── park_metadata_builder.py        ← NEW: static 30-park table (orientation + roof)
└── weather_backfill.py             ← NEW: batch fetch historical per game_pk

data/features/
├── park_metadata.parquet           ← NEW (30 rows, static)
└── game_weather.parquet            ← NEW (one row per game_pk)

sports/mlb/
├── park_metadata_live.py           ← NEW
└── weather_live.py                 ← NEW (open-meteo forecast for today's games)

scripts/
├── refresh_weather_daily.py        ← NEW
└── cron/run_refresh_weather_daily.bat

data/state_snapshot_builder.py      ← emit in_extras + ghost_runner flag on snapshot rows
data/feature_store.py               ← 5 new features in enrichment; 34→39 cols
sports/mlb/winprob_inference.py     ← phase4_extras param
integration/recommendation_api.py   ← wire phase4_extras
core/selfcheck.py                   ← EXPECTED_FEATURE_COUNT = 39
models/audit_features.py            ← PHASE4_NEW_FEATURES constant
scripts/cron/install_scheduled_tasks.bat  ← +1 task (7 total)
```

## §2 Features added (34 → 39)

| # | Column | Description |
|---|---|---|
| 35 | `wind_out_mph` | Wind projected onto park's outfield axis. +=blowing out. Clamped ±30. 0 for indoor/closed roof. |
| 36 | `temp_f` | Game-time temperature. 70°F default for indoor (neutral). |
| 37 | `is_roof_closed` | Binary. 1 if indoor or retractable closed. |
| 38 | `in_extras` | Binary. 1 if `inning > 9`. |
| 39 | `ghost_runner_on_2nd` | Binary. 1 if `in_extras AND season >= 2020 AND outs == 0`. MLB ghost-runner rule. |

## §3 Park metadata schema

`park_metadata.parquet`:

| Column | Description |
|---|---|
| park_id | Retrosheet ParkID (matches `park_factors.parquet`, `snapshots.park_id`) |
| park_name | Human-readable stadium name |
| latitude | Decimal degrees (weather API needs lat/lon) |
| longitude | Decimal degrees |
| outfield_orientation_deg | Compass bearing of home plate → CF axis. Wind blowing *from* this direction is blowing out. |
| has_roof | 0/1 |
| is_retractable | 0/1 (if has_roof=1, can also be open) |
| is_indoor | 0/1 (always closed, e.g. Tropicana) |

Hand-coded from public stadium data. 30 rows total.

## §4 Weather data (Open-Meteo)

Endpoints:
- Archive (historical): `https://archive-api.open-meteo.com/v1/archive?latitude=...&longitude=...&start_date=...&end_date=...&hourly=temperature_2m,wind_speed_10m,wind_direction_10m`
- Forecast (today/near-future): `https://api.open-meteo.com/v1/forecast?latitude=...&longitude=...&hourly=...`

**Free tier:** 10k requests/day (plenty for MLB). No API key needed.

**Sampling:** Use the hourly reading closest to `commence_time`. One row per `game_pk`.

**Wind projection:**
```
wind_out_mph = wind_speed * cos((wind_from_direction_deg - outfield_orientation_deg) * π/180)
```
A north wind (wind_from=0°) at Coors (orientation=10° roughly N-NE toward CF) blows out (positive). Yankee Stadium (orientation~45° NE) gets same north wind as partial out (cos(−45°)=0.71).

Closed-roof games: `wind_out_mph = 0`, `temp_f = 70`.

## §5 Extras-inning features

No new parquet needed. Derived at feature_store time:

```python
out["in_extras"] = (df["inning"] > 9).astype(float)
out["ghost_runner_on_2nd"] = (
    (df["inning"] > 9) & (df["season"] >= 2020) & (df["outs"] == 0)
).astype(float)
```

Snapshot builder also adds these two columns at snapshot-creation time so they're available live.

## §6 Audit gates

Same framework (ablation + SHAP + tradable-lift + PROMOTE_MARGINAL floor at -0.003).

## §7 Error handling

| Failure | Response |
|---|---|
| Open-Meteo API down | Live: impute neutral (70°F, 0 wind, roof_closed=1). Backfill: retry later. |
| Unknown park_id | Treat as indoor neutral |
| Historical archive lag (< 3d) | Backfill skips recent games; daily refresh catches up |

## §8 Realistic outcome expectations

- Weather lifts HR rate ~2-5% in extreme conditions → maybe 0.002 log-loss improvement
- Extras-inning features affect <1% of snapshot rows → low SHAP signal
- **Most likely audit outcome: PROMOTE_MARGINAL** (weather shows some SHAP, ablation near-neutral)
- Worst case REJECT (features don't lift aggregate log loss)

## §9 Cron

7th scheduled task: `mlb-weather-daily` @ 09:15 CT. Fetches weather for today's games + backfills any missing for yesterday.

## Out of scope

- **Umpire quality** — separate sub-project if operator wants; different data source entirely
- **Jet stream / large-scale weather patterns**
- **Precipitation/rain-delay modeling**
- **Temperature interaction with home_sp_quality** — audit will show if we need it
