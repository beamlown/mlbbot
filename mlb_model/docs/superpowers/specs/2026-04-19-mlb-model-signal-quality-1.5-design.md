# MLB Model Signal Quality — Sub-Project #1.5 Design

**Date:** 2026-04-19
**Status:** Approved (brainstorming complete)
**Sub-project scope:** Audit-ready snapshots + daily cron triggers
**Parent:** sub-project #1 shipped 2026-04-19; #2 (batter quality) is next after this

## Context

Sub-project #1 shipped 8 phase-1 features (pitcher quality + park factors + sharp pregame prior) but with a known operational gap: historical snapshots don't carry `park_id` and the `pitcher_quality.parquet` keys on pybaseball-derived names while snapshots key on Statcast MLBAM int IDs. Result: `feature_store.enrich_with_phase1_features()` falls back to neutral defaults during offline training, and the audit step would REJECT phase-1 features for "no signal" — masking whether the features are actually useful.

This sub-project closes that gap with the smallest possible code surface, then adds three daily scheduled triggers so the operator never has to remember to refresh Elo, sharp odds, or pitcher quality manually.

## Locked decisions

| Decision | Choice |
|---|---|
| Pitcher data source | **B-statcast** — replace `build_from_pybaseball` with `build_from_statcast` aggregating local pitch data; MLBAM IDs match snapshots natively, no external API |
| Park ID source | Hand-coded `home_team → park_id` map (32 entries) in `sports/mlb/parks.py`; neutral 1.0 fallback for unknowns |
| Cron timing | 3 daily UTC triggers — Elo @ 11:00, Pitcher Quality @ 13:00, Sharp Odds @ 14:00 |
| Cron mechanism | `superpowers:schedule` (Claude Code remote triggers); not OS-level cron |
| `pregame_prior_source` for historical rows | Always `1` (elo) — that's what was used pre-2026 |

## §1 Architecture / file map

```
data/foundation/
├── pitcher_quality_builder.py         ← MODIFY: add build_from_statcast(); leave
│                                        build_from_pybaseball as DEPRECATED
├── park_factor_builder.py             ← (no change)
└── statcast_pitcher_aggregator.py     ← NEW: aggregate pitches → per-(pitcher_id,
                                        game_date) FIP rows

data/
├── state_snapshot_builder.py          ← MODIFY: emit park_id + pregame_prior_source
└── feature_store.py                   ← (no change — joins start working as soon as
                                        snapshots have park_id)

sports/mlb/
└── parks.py                           ← NEW: TEAM_TO_PARK static map + lookup helper

scripts/
└── refresh_pitcher_quality_daily.py   ← NEW: incremental aggregator + append to parquet
                                        (existing update_elo_daily.py, update_sharp_odds_daily.py
                                         reused)

# Remote triggers via superpowers:schedule (no files):
mlb-elo-daily               0 11 * * *  → scripts/update_elo_daily.py
mlb-pitcher-quality-daily   0 13 * * *  → scripts/refresh_pitcher_quality_daily.py
mlb-sharp-odds-daily        0 14 * * *  → scripts/update_sharp_odds_daily.py
```

## §2 Snapshot schema additions

Two new columns on every snapshot row. Zero impact on the 22 base features (the model never reads them directly — they only flow into the enrichment join).

| Column | Source | Purpose |
|---|---|---|
| `park_id` | `sports.mlb.parks.TEAM_TO_PARK[home_team]` | Joins to `park_factors.parquet` |
| `pregame_prior_source` | constant `1` (elo) for all historical rows | Tells the model how trustworthy the prior was |

Existing snapshot columns (already present, verified): `game_id, date, season, home_team, away_team, inning, half, outs, home_score, away_score, score_diff, base_state, base_state_value, outs_elapsed, game_progress, home_pitcher_id, away_pitcher_id, home_pitch_count, away_pitch_count, home_tto, away_tto, home_is_bullpen, away_is_bullpen, pregame_win_prob, home_elo, away_elo, home_won_final` — 27 columns.

After this sub-project: 29 columns.

## §3 Pitcher quality from Statcast (replacing pybaseball)

`data/foundation/statcast_pitcher_aggregator.py` reads `data/raw/statcast/YYYY_MM.parquet` files, groups by `(pitcher, game_pk)`, computes per-game:

```python
ip   = (events_that_record_outs.count() / 3)        # use 'events' field
k    = events.isin(['strikeout', 'strikeout_double_play']).sum()
bb   = events.isin(['walk', 'hit_by_pitch']).sum()  # HBP optional; default yes
hr   = (events == 'home_run').sum()
fip  = (13*hr + 3*bb - 2*k) / ip + 3.2
```

Output DataFrame: `(pitcher_id, game_date, ip, fip, season)` — pitcher_id is MLBAM int, matches `snapshot.home_pitcher_id` natively.

The pure compute function `compute_pitcher_quality_pointtime` from sub-project #1 is unchanged — it doesn't care where the source data comes from. Only the loader is replaced.

`build_from_pybaseball` is preserved in `pitcher_quality_builder.py` as DEPRECATED but not deleted (in case anything imports it). New `build_from_statcast(seasons)` becomes the documented path.

## §4 Daily cron triggers

Created via `superpowers:schedule` skill. Each is a remote Claude Code agent that fires on the cron schedule, runs the corresponding script, and reports row counts / errors.

| Trigger name | Cron (UTC) | Script | Notes |
|---|---|---|---|
| `mlb-elo-daily` | `0 11 * * *` | `scripts/update_elo_daily.py` | After overnight games settle |
| `mlb-pitcher-quality-daily` | `0 13 * * *` | `scripts/refresh_pitcher_quality_daily.py` | Incremental — appends yesterday's pitches only |
| `mlb-sharp-odds-daily` | `0 14 * * *` | `scripts/update_sharp_odds_daily.py` | Mid-day, prices firm |

Trigger agent prompt template (~1-2 lines): "cd to `C:/Users/johnny/Desktop/mlb_model`, run `python <script>`, report stdout's last 5 lines. If exit code != 0, surface the error."

Triggers are idempotent — re-running same day is safe (Elo updater de-dups by date; pitcher aggregator skips already-processed games; sharp odds appends but operator can post-dedupe).

## §5 Error handling

| Failure | Response |
|---|---|
| Statcast aggregation finds 0 pitches yesterday (off day, Statcast lag) | Script logs "no new games yesterday" and exits 0 |
| `data/raw/statcast/YYYY_MM.parquet` for current month missing | Script logs ERROR, exits 1; operator extends Statcast scraper |
| `park_id` lookup misses (e.g., relocated team) | Returns `"unknown"`; live `lookup_park_factor` returns neutral 1.0 |
| Cron trigger itself fails (agent dispatch error) | Visible in `superpowers:schedule` trigger list; operator re-runs via `mcp__schedule__schedule_run` |
| Pitcher quality parquet corrupt mid-append | Script writes to `.tmp` then atomic rename; on detection, restore from prior day's archive |

## §6 Testing

**Unit tests (in `tests/`):**
- `test_statcast_pitcher_aggregator.py` — synthetic 5-pitch frame → exact FIP value; edge cases (0 IP, all walks, no events)
- `test_parks.py` — every standard MLB team resolves to a park_id; unknown team returns `"unknown"`

**Integration tests (in `tests/integration/`):**
- Extend existing `test_full_pipeline.py` to include the new statcast → pitcher_quality path with a 100-game synthetic season

**Manual smoke after retrain (operator):**
- `python scripts/retrain_after_features.py`
- Inspect `artifacts/audit_report.json` — at least one phase-1 feature should now show non-zero ablation delta and a non-trivial SHAP rank, vs the all-imputed REJECT verdict we'd see without this fix

## Out of scope

- **Sub-project #2** (batter quality, lineup, platoon) — separate spec/plan
- **Sub-projects #3–#4** (bullpen leverage, weather, extras) — separate specs/plans
- **Statcast scraper extension** to current month — assumes operator's existing scraper covers through yesterday
- **Mid-season park relocation handling** — manual `TEAM_TO_PARK` map update if needed
- **Pitcher quality refresh historical backfill** — assumed already-built parquet from sub-project #1 stays as-is; daily cron only appends going forward
