# MLB Model Signal Quality — Sub-Project #1 Design

**Date:** 2026-04-19
**Status:** Approved (brainstorming complete, awaiting implementation plan)
**Sub-project scope:** Pitcher quality + Park factors + Pregame prior fix
**Parent decomposition:** 4 sub-projects (1: cheap wins, 2: roster/lineup, 3: bullpen/leverage, 4: weather/extras). This doc covers #1 only.

## Context

Current MLB win-probability model (`mlb_winprob_v1_lgbm`) is well-calibrated (Brier 0.156, mean cal-error 1.8%, promoted) but its 22-feature input vector is almost entirely **game state** (score, inning, base/out, pitcher fatigue, pregame Elo). It carries zero domain features for batter quality, lineup turnover, weather, park, bullpen quality, or umpire. The pregame prior pipeline frequently falls back to a 0.54 default because the Elo table built from 2018–2025 isn't refreshed for the 2026 season.

This sub-project adds **8 new features** drawn from cheap, high-value sources (pitcher seasonal/recent-form stats, park run factors, sharp-odds-primary pregame prior with Elo fallback) and gates their inclusion behind an **ablation + SHAP + tradable-lift audit** so we never widen the feature vector with noise.

## Design decisions (locked during brainstorming)

| Question | Decision |
|---|---|
| Pitcher quality window | **D — Hybrid (0.6×current STD + 0.4×prior season, regressed to mean) + recent-form (trailing 30-day delta)** |
| Pregame prior fallback chain | **C — Sharp odds primary (Pinnacle via the-odds-api), daily-updated Elo fallback, no 0.54 default** |
| Park factor granularity | **A — Single 3-year rolling run-scoring factor per park** |

## §1 Architecture

```
data/foundation/                    ← NEW: domain-data ingest
├── pitcher_quality_builder.py      ← season + recent-form rolling stats per pitcher
├── park_factor_builder.py          ← 3-year rolling run-factor table per park
└── sharp_odds_fetcher.py           ← daily snapshot of Pinnacle moneyline odds

data/features/
├── pitcher_quality.parquet         ← (pitcher_id, date) → 8 stat columns
├── park_factors.parquet            ← (park_id, season) → run_factor
├── elo_table.parquet               ← UPDATED: daily refresh job
├── sharp_odds_history.parquet      ← (game_pk, fetched_at) → home_prob
└── features_all.parquet            ← REGENERATED with new columns

sports/mlb/
├── pitcher_quality_live.py         ← NEW: lookup live pitcher stats by id+date
├── park_factor_live.py             ← NEW: lookup park factor by venue
└── winprob_inference.py            ← UPDATED: feature vector +9 cols

scripts/
├── update_elo_daily.py             ← NEW: cron job
├── update_sharp_odds_daily.py      ← NEW: cron job
└── retrain_after_features.py       ← NEW: rerun train→cal→eval→audit→promote

models/
└── audit_features.py               ← NEW: ablation + SHAP + tradable-lift gates
```

The model itself isn't restructured — we widen the feature vector and re-run the existing train→calibrate→evaluate→promote pipeline, with a new audit step inserted before promotion.

## §2 Features added (22 → 30)

All new features are computed **point-in-time**: only data available *before* game start may be used. No leakage.

| # | Column | Source | Description |
|---|---|---|---|
| 23 | `home_sp_quality` | `pitcher_quality.parquet` | Hybrid FIP-: `0.6×current_STD + 0.4×prior_season`, regressed to league mean by IP. (FIP- scale: 100 = league avg, lower = better.) |
| 24 | `away_sp_quality` | `pitcher_quality.parquet` | Same, away starter |
| 25 | `home_sp_recent_form` | `pitcher_quality.parquet` | Trailing 30-day FIP delta vs hybrid baseline (positive = pitching better than baseline) |
| 26 | `away_sp_recent_form` | `pitcher_quality.parquet` | Same, away starter |
| 27 | `sp_quality_diff` | derived | `away_sp_quality − home_sp_quality` (positive = home has better SP) |
| 28 | `park_run_factor` | `park_factors.parquet` | 3-year rolling run factor (1.00 = neutral, >1 = hitter-friendly) |
| 29 | `park_run_factor_x_late` | derived | `(park_factor − 1.0) × late_game` — park matters more when scoring matters most |
| 30 | `pregame_prior_source` | derived | 0=sharp, 1=elo, 2=default — lets model learn to weight prior trust |

**Pregame prior re-sourcing:** existing feature #1 `pregame_logit` is RE-SOURCED (not removed, no schema break). It now reads sharp Pinnacle prior first, daily-Elo second, never the 0.54 default. Companion flag #30 `pregame_prior_source` tells the model which source produced the value, so it can learn to discount Elo-sourced and default-sourced priors. Net effect: the prior signal becomes meaningfully sharper in 2026 without adding a redundant column.

## §3 Data flow

### Offline (training pipeline, run once after each new feature group lands)

```
1. pybaseball.statcast(2018..2025)        → data/raw/statcast/YYYY_MM.parquet (already exists)
2. pybaseball.pitching_stats_range        → pitcher_quality_builder.py
                                           → pitcher_quality.parquet (per pitcher_id, per date)
3. retrosheet game logs                   → park_factor_builder.py
                                           → park_factors.parquet (per park, per season)
4. historical sharp odds (or backfill)    → sharp_odds_history.parquet
5. feature_store.py REGEN                 → features_all.parquet (now 31 columns)
6. train_lightgbm.py                      → winprob_model.pkl
7. calibrate_model.py (2024)              → calibrator.pkl
8. evaluate_model.py (2025)               → evaluation_results.json
9. audit_features.py (NEW — see §4)       → audit_report.json
10. promotion check                       → artifacts deployed only if all gates PASS
```

### Live (every recommendation loop)

```
snap = get_game_snapshot()                          # unchanged
pregame_prob = sharp_odds_live() or elo_live()      # NEW: never falls back to 0.54
sp_quality = pitcher_quality_live(home_sp_id, away_sp_id, snap.date)
park_factor = park_factor_live(snap.venue)
features = build_feature_vector(snap, pregame_prob, sp_quality, park_factor)
p_home = calibrator(model.predict(features))
```

## §4 Audit & validation

Before any new feature ships, it must **earn its slot**. New `models/audit_features.py` runs after `evaluate_model.py` and produces `artifacts/audit_report.json`. Three independent tests per feature group:

| Test | What it measures | Pass threshold |
|---|---|---|
| **Ablation** | Train two models — with new features, without — on identical splits. Compare test log loss & Brier. | New features must improve test log loss by **≥ 0.005** (≈1% relative) — else dropped. |
| **SHAP global importance** | Mean absolute SHAP value per feature on 2025 test set. | New feature must rank in top 50% of all features OR show interaction (verified by SHAP interaction values). |
| **Tradable-bucket lift** | Among trades flagged actionable (edge ≥ 5%), bucket by feature value (low/mid/high) and measure win rate. | High-value bucket must beat low-value bucket by ≥ **3pp** for "edge-relevant" verdict. |

**Audit report format:**

```json
{
  "feature_group": "pitcher_quality",
  "ablation": {"with": 0.4612, "without": 0.4653, "delta": 0.0041, "passed": false},
  "shap": {"home_sp_quality": 0.083, "rank": 6, "passed": true},
  "tradable_lift": {"high_q_pct_winners": 0.612, "low_q_pct_winners": 0.581, "delta": 0.031, "passed": true},
  "verdict": "PROMOTE_WITH_CAVEAT — passes shap+lift, fails ablation"
}
```

**Verdict logic:** ship to prod only if **ablation PASS** AND (**shap PASS** OR **tradable_lift PASS**). Ablation is the hard gate — a feature that doesn't lower test log loss is noise. Audit report committed to git alongside the deployment manifest.

## §5 Error handling

Each new data path has a defined failure behavior — never silently fall back to garbage:

| Failure | Detection | Response |
|---|---|---|
| Sharp odds API down | HTTP timeout / non-200 | Log WARN, fall back to live Elo, set `pregame_prior_source=1` |
| Live Elo lookup misses | `get_pregame_prob` returns 0.54 default | Log ERROR, set `pregame_prior_source=2`, lower `data_quality` by 0.10 |
| Pitcher quality lookup fails | parquet returns no row | Substitute league-mean FIP- (regressed), set `home_sp_quality_imputed=1` flag |
| Park factor missing | venue not in table | Use neutral 1.00, log WARN |
| Daily Elo cron fails | `elo_table.parquet` mtime > 36h | Startup self-check raises HALT (refuses trades on stale prior) |
| Sharp odds back-fill mismatch | game_pk has no row | Use Elo, mark `pregame_prior_source=1` in training data — same source flag in train and live |

**Critical invariant:** the model is trained on the **same fallback distribution** it sees in production. If 8% of training games have `pregame_prior_source=1`, that's fine — the model learns to weight that prior less. If we trained on 100% sharp and live runs 60% Elo fallback, that's a silent distribution shift.

## §6 Testing strategy

**Unit tests** (per new module, in `tests/`):
- `test_pitcher_quality_builder.py` — point-in-time correctness: a query for date D returns no PA from date ≥ D
- `test_park_factor_builder.py` — 3-year rolling math, neutral park ≈ 1.00 across years
- `test_sharp_odds_fetcher.py` — mock API responses (200/timeout/malformed), verify fallback chain
- `test_winprob_inference.py` — feature vector length = 30; missing inputs trigger imputation + flag

**Integration tests** (`tests/integration/`):
- `test_full_pipeline.py` — synthetic 100-game season → run pipeline end-to-end → verify artifacts produced + audit report passes thresholds
- `test_inference_parity.py` — same snapshot through old (22-feature) and new (30-feature) pipelines, verify only the new 8 columns differ (plus re-sourced `pregame_logit` value when sharp odds were available)

**Backtest validation:**
- After retrain, replay all 2025 shadow recommendations through the new model
- Compare: trade count, edge distribution, would-have-been-win-rate vs old model
- New model must be **non-worse** on action-rate-adjusted Brier (no overconfident new trades)

**Regression guard:** existing `selfcheck.py` extended with — feature count == manifest expectation, all new data files present and < 36h old, sharp odds API reachable (or explicit "stale-Elo-only" mode acknowledged).

## Out of scope

- **Batter quality, lineup, platoon features** — Sub-project #2
- **Bullpen quality, leverage index, closer-warming signal** — Sub-project #3
- **Weather, extras-inning model** — Sub-project #4
- **Bot-side execution gates** — `sports_bot_v2` keeps full authority over cooldown/risk/position; this sub-project only changes what `get_recommendations()` returns
- **Phase 3 merged-mode integration** — still gated on the parent integration roadmap; this sub-project lands in shadow mode first

## Operational notes

- **API key:** sharp-odds source requires `ODDS_API_KEY` env var (the-odds-api.com Pinnacle tier). Code degrades gracefully to Elo-only if unset; startup logs a clear warning.
- **Retrain cadence:** one-shot retrain at end of this sub-project. Weekly/monthly retrain cron is a follow-up (not in scope).
- **Compute cost:** retrain uses existing 1.38M-row feature_store; LightGBM on 30 cols × 1.4M rows is a few minutes on the existing machine. SHAP audit is the slowest step (~5–10 min for 2025 test slice).
- **Rollback:** old artifacts stay in `artifacts/archive/<timestamp>/` until the new model passes a 7-day shadow-mode parity check. `selfcheck.py` can pin to archived version via env var.
