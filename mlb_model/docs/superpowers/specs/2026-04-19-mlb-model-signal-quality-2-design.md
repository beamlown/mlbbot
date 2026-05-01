# MLB Model Signal Quality — Sub-Project #2 Design

**Date:** 2026-04-19
**Status:** Approved (auto-mode push)
**Scope:** Batter quality + lineup features (current batter, upcoming, platoon)
**Parent:** #1 + #1.5 shipped 2026-04-19; #3 (bullpen/leverage) and #4 (weather/extras) still queued

## Locked decisions

| Question | Choice |
|---|---|
| Granularity | **B** — current + upcoming batter (not lineup-only, not full kitchen-sink) |
| Stat | **xwOBA** from Statcast (not wOBA, not wRC+) — quality of contact, MLBAM-id native, pybaseball-free |
| Window | **C** — hybrid (`0.6×current_STD + 0.4×prior_season`), regressed to league mean by PA, no recent-form delta |
| Upcoming | **C** — current batter explicit + next-3 rollup average |
| Platoon | **A** — binary platoon advantage flag (audit decides if it earns a slot) |

## §1 Architecture / file map

```
data/foundation/
├── statcast_batter_aggregator.py    ← NEW: pitches → per-PA xwOBA per batter
└── batter_quality_builder.py        ← NEW: point-in-time hybrid xwOBA

sports/mlb/
├── batter_quality_live.py           ← NEW: (batter_id, date) → xwOBA
└── lineup_live.py                   ← NEW: MLB Stats API current batter + lineup

data/
├── state_snapshot_builder.py        ← MODIFY: 7 new columns
└── feature_store.py                 ← MODIFY: 5 new features in enrichment

scripts/
├── refresh_batter_quality_daily.py  ← NEW: incremental daily refresh
└── cron/
    └── run_refresh_batter_quality_daily.bat  ← NEW: Windows wrapper

integration/recommendation_api.py    ← MODIFY: wire phase2_extras
core/selfcheck.py                    ← MODIFY: feature count 30 → 35
sports/mlb/game_state_service.py     ← MODIFY: include current batter + lineup from MLB Stats API

# 4th scheduled task: mlb-batter-quality-daily @ 08:30 CT
```

## §2 Features added (30 → 35)

| # | Column | Description |
|---|---|---|
| 31 | `current_batter_xwoba` | Hybrid xwOBA scaled to 100=avg (lower scale = below avg) for the batter currently at the plate |
| 32 | `next3_avg_xwoba` | Mean hybrid xwOBA for on-deck + in-the-hole + next-up (3 upcoming batters) |
| 33 | `lineup_avg_xwoba` | Mean hybrid xwOBA across all 9 batters in the batting order |
| 34 | `current_batter_platoon_advantage` | Binary: 1 if current batter has handedness advantage vs current pitcher (L vs R, R vs L, switch always 1); 0 otherwise |
| 35 | `current_batter_xwoba_x_late` | Derived: `(current_batter_xwoba − 100) × late_game` — leverage interaction |

xwOBA values are scaled from raw (~.250-.450 scale) to a 100-centered scale via `(xwoba / league_avg_xwoba) × 100`. Lower 100 = below average, higher = above. (Note: this inverts the FIP- direction. We use the conventional batter direction: higher = better, opposite of FIP-.)

## §3 Snapshot schema additions (29 → 36 columns)

7 new fields per snapshot row, all derivable from Statcast pitch data:

| Column | Type | Source |
|---|---|---|
| `batter_id` | int (MLBAM) | Statcast `batter` |
| `batter_stand` | str (L/R/S) | Statcast `stand` |
| `home_pitcher_p_throws` | str (L/R) | Statcast `p_throws` (filtered to home pitcher's row) |
| `away_pitcher_p_throws` | str (L/R) | Statcast `p_throws` (filtered to away pitcher's row) |
| `home_lineup_ids` | list[int] | First-9 unique batters from home half-innings |
| `away_lineup_ids` | list[int] | First-9 unique batters from away half-innings |
| `current_lineup_position` | int (1-9) | Computed from lineup ID list lookup |

All these come from data we already have in `data/raw/statcast/`. Pure-compute derivation in the snapshot builder.

## §4 Live data — current batter + lineup feed

`sports/mlb/lineup_live.py`:
- Endpoint: `https://statsapi.mlb.com/api/v1/game/{gamePk}/feed/live`
- Returns:
  - `current_batter_id` (int)
  - `current_batter_stand` (L/R/S)
  - `current_pitcher_p_throws` (L/R)
  - `home_lineup` (list[int], 9 entries)
  - `away_lineup` (list[int])
  - `current_lineup_position` (1-9)
- Cache TTL: 15s (matches recommendation loop cadence)
- Failure mode: returns `None`; live inference imputes neutral (current_batter_xwoba=100, next3=100, lineup=100, platoon=0, batter_imputed=True)

This is a NEW live data source. ESPN's summary endpoint sometimes has batter info but it's inconsistent — MLB Stats API is canonical and free.

`sports/mlb/game_state_service.py` is extended to call `lineup_live.fetch(gamePk)` after the existing ESPN summary call and merge the result into the snapshot object as new attributes (`current_batter_id`, `current_lineup`, etc.).

## §5 Audit framework — same as #1

The existing `models/audit_features.py` framework is reused with `PHASE2_NEW_FEATURES = ["current_batter_xwoba", "next3_avg_xwoba", "lineup_avg_xwoba", "current_batter_platoon_advantage", "current_batter_xwoba_x_late"]`. Same gates:

- Ablation: log-loss delta ≥ 0.005 vs phase-1 baseline
- SHAP: at least one new feature in top 50%
- Tradable lift: at least one new feature shows ≥3pp delta in high-vs-low bucket of edge≥5% trades

If `lineup_avg_xwoba` and `next3_avg_xwoba` are highly correlated and only one passes lift, drop the redundant one. Verdict logic: PROMOTE if (ablation pass AND (shap or lift)); REJECT if ablation fails; PROMOTE_WITH_CAVEAT otherwise.

## §6 Error handling

| Failure | Response |
|---|---|
| MLB Stats API timeout | Live lookup returns None; recommendation imputes neutral; logs WARN |
| Batter quality lookup misses (rookie, scratched starter) | Substitute league-mean xwoba=100, set `current_batter_imputed=True`, lower data_quality by 0.05 |
| Statcast `xwoba` field absent (early-2015 data) | Filter out — only seasons with reliable xwoba (2018+) are usable |
| Lineup parse fails (DH change mid-game, lineup card incomplete) | Falls back to first-9-unique-PAs heuristic from snapshot data; logs INFO |

## §7 Testing

**Unit tests:**
- `test_statcast_batter_aggregator.py` — synthetic 5-PA frame → expected xwOBA aggregate; edge cases (0 PA, all-walks, missing xwoba field)
- `test_batter_quality_builder.py` — point-in-time correctness leak guard (parallel to pitcher quality builder tests)
- `test_batter_quality_live.py` — known batter, unknown batter imputes 100, fall-back to most-recent-prior-date
- `test_lineup_live.py` — mocked MLB Stats API response → parsed correctly; timeout → None

**Integration:** extend `tests/integration/test_full_pipeline.py` with batter aggregation path

**Manual smoke:** after retrain, `audit_report.json` should show batter features earning slots (or being correctly rejected if they don't).

## §8 Operational — 4th daily cron task

Add to `scripts/cron/`:
- `run_refresh_batter_quality_daily.bat` — wrapper for `python scripts/refresh_batter_quality_daily.py`
- Update `install_scheduled_tasks.bat` to include this 4th task at 08:30 CT (between pitcher quality at 08:00 and sharp odds at 09:00)
- Update runbook with the new task

## Out of scope

- **Pitcher-handedness-specific xwOBA splits** (option B from platoon question) — defer to #2.5 if binary flag underperforms
- **Bullpen leverage** — sub-project #3
- **Weather + extras** — sub-project #4
- **Lineup-card scrape from MLB Stats API for pre-game posting** — only "current batter" used live; full lineup is reconstructed from PA sequence
