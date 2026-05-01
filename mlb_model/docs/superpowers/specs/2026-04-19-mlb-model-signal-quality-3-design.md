# MLB Model Signal Quality — Sub-Project #3 Design

**Date:** 2026-04-19
**Status:** Approved (auto-mode)
**Scope:** Bullpen quality + leverage index
**Parent:** #1, #1.5, #2 shipped 2026-04-19; #4 (weather/extras) remains queued

## Locked decisions

| Decision | Choice |
|---|---|
| Reliever stat | Relief-FIP (Statcast, IP<4.0 filter — inverse of starter filter), MLBAM-id native |
| Team bullpen aggregate | Weighted mean relief-FIP- across 8 most-active relievers, trailing 30 days |
| Leverage index | Static table lookup (inning × outs × base_state × score_diff) built once from historical RE24 |
| Closer-warming | SKIP v1 (external, inconsistent). Deferred to #3.5 if audit warrants |

## §1 Architecture / file map

```
data/foundation/
├── statcast_reliever_aggregator.py     ← NEW
├── reliever_quality_builder.py         ← NEW
├── bullpen_aggregator.py               ← NEW (rolling team-level)
└── leverage_index_builder.py           ← NEW (static table)

data/features/
├── reliever_quality.parquet            ← NEW
├── bullpen_quality.parquet             ← NEW
└── leverage_index.parquet              ← NEW (static)

sports/mlb/
├── reliever_quality_live.py            ← NEW
├── bullpen_quality_live.py             ← NEW
└── leverage_index_live.py              ← NEW

scripts/
├── refresh_reliever_quality_daily.py   ← NEW
├── refresh_bullpen_quality_daily.py    ← NEW
└── cron/
    ├── run_refresh_reliever_quality_daily.bat
    └── run_refresh_bullpen_quality_daily.bat

# Modified:
data/feature_store.py                   ← FEATURE_COLUMNS 35 → 40 + phase-3 enrichment
sports/mlb/winprob_inference.py         ← phase3_extras param + 5 new features
integration/recommendation_api.py       ← wire phase3_extras
core/selfcheck.py                       ← EXPECTED_FEATURE_COUNT = 40
models/audit_features.py                ← PHASE3_NEW_FEATURES constant
scripts/cron/install_scheduled_tasks.bat ← +2 new tasks (6 total)
docs/runbook.md                         ← new cron entries
tests/integration/test_full_pipeline.py ← reliever path
```

## §2 Features added (35 → 40)

| # | Column | Description |
|---|---|---|
| 36 | `home_reliever_quality` | Relief-FIP- for home's current pitcher when `home_is_bullpen=1`; falls back to `home_sp_quality` (#1 starter quality) when starter still in game |
| 37 | `away_reliever_quality` | Same, away side |
| 38 | `home_bullpen_avg_quality` | Team-level rolling bullpen FIP- (8 most-active relievers, trailing 30d) |
| 39 | `away_bullpen_avg_quality` | Same, away side |
| 40 | `leverage_index` | Static table lookup by (inning, outs, base_state, score_diff). Normalized: 1.0 = league-average PA leverage |

No new snapshot columns required — all derivable from existing `home_pitcher_id`, `home_is_bullpen`, `inning`, `outs`, `base_state`, `score_diff`, `home_team`, `away_team`.

## §3 Relief-FIP aggregation

`data/foundation/statcast_reliever_aggregator.py`:
- Mirrors pitcher aggregator from #1.5 BUT filters `ip < 4.0` (relief outings).
- Same FIP formula: `(13×HR + 3×BB − 2×K) / IP + 3.2`
- Scaled to 100-center like sp_quality (lower = better).

## §4 Rolling bullpen aggregate

`data/foundation/bullpen_aggregator.py`:
- For each `(team, date)`: find the 8 pitchers with the most relief appearances in the trailing 30 days, compute their weighted-by-IP average relief-FIP.
- Team assignment derived from Statcast `home_team` / `away_team` columns based on which side they pitched for (inning_topbot).
- Output: `(team, as_of_date, bullpen_avg_fip, n_relievers)`.

## §5 Leverage index (static table)

`data/foundation/leverage_index_builder.py`:
- For each (inning, outs, base_state, score_diff_bucket), compute historical win-probability swing per PA from Statcast PAs + game outcomes.
- Normalize: divide by average swing per PA league-wide → 1.0 = average leverage.
- Score diff buckets: {-4, -3, -2, -1, 0, +1, +2, +3, +4, |>4|} = 10 buckets.
- Total table size: 9 innings × 3 outs × 8 base states × 10 score buckets = 2160 rows (tiny).
- Built ONCE from 2018-2025 data, no daily refresh needed.

Live lookup: `sports/mlb/leverage_index_live.py.lookup(inning, outs, base_state, score_diff) → float`.

## §6 Audit gates

Existing `models/audit_features.py` framework reused. `PHASE3_NEW_FEATURES = ["home_reliever_quality", "away_reliever_quality", "home_bullpen_avg_quality", "away_bullpen_avg_quality", "leverage_index"]`. Same thresholds: ablation ≥0.005 log-loss delta AND (SHAP top-50% OR tradable lift ≥3pp).

Expected signal: `home_reliever_quality` should be the strongest (direct impact when bullpen in); `leverage_index` strong in late-game; bullpen-avg may be redundant with reliever quality and could be dropped.

## §7 Error handling

| Failure | Response |
|---|---|
| Pitcher not in reliever_quality (starter, or not yet relief) | Use `home_sp_quality` from phase-1 as fallback; set `home_reliever_imputed=True` |
| Bullpen parquet missing / empty | Fall back to league-mean 100, log WARN |
| Leverage lookup misses (unknown state, extras beyond 12 innings) | Default to 1.0 (neutral), log INFO |

## §8 Testing

**Unit tests:**
- `test_statcast_reliever_aggregator.py` — IP<4.0 filter + FIP math
- `test_reliever_quality_builder.py` — point-in-time leak guard
- `test_bullpen_aggregator.py` — 30-day rolling, top-8 selection
- `test_leverage_index_builder.py` — static table math
- `test_reliever_quality_live.py` / `test_bullpen_quality_live.py` / `test_leverage_index_live.py` — standard fallback patterns

**Integration:** extend `tests/integration/test_full_pipeline.py` with bullpen path

## §9 Operational

Two new scheduled tasks at 08:15 CT (reliever) and 08:45 CT (bullpen). Leverage index is static (no cron).

Operator bootstrap:
```cmd
python -m data.foundation.leverage_index_builder
python -m data.foundation.reliever_quality_builder
python -m data.foundation.bullpen_aggregator
```
Then rerun `install_scheduled_tasks.bat` (now installs 6 tasks).

## Out of scope

- **Closer-warming signal** — #3.5 if audit shows reliever features promising
- **Reliever freshness** (days-rest, back-to-back) — #3.5
- **Handedness-split relief stats** — #3.5
- **Sub-project #4** — weather + extras-inning model
