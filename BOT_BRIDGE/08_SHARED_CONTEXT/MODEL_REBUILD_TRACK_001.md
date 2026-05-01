# MODEL_REBUILD_TRACK_001
## Manager artifact — Supervisor + Analytical Specialist Mode
## Date: 2026-04-11

## Current source-of-truth state
- Track A runtime/config activation is repaired and runtime-proven.
- Execution/dashboard plumbing is no longer the primary blocker.
- Strategy has no proven edge.
- Confidence is not proven predictive and higher-confidence buckets remain poor.
- Results are excessively concentrated in a few trades and one slug.
- Current recommendation remains: pause/redesign, paper-only observation mode until model quality improves.

## Core principle
Stop guessing. Rebuild the model from evidence.
Use existing mlb_model data, existing shadow recommendation logs, trade/outcome history, a current-season MLB stats backfill, and a daily previous-day stats updater to create a trustworthy model-quality recovery track.

## Workstream separation

### 1. Data pipeline tasks
Goal: establish a complete, versioned, trustworthy MLB season data foundation.

### 2. Model audit tasks
Goal: identify what the current model actually sees, how signals are formed, and where quality breaks.

### 3. Feature engineering tasks
Goal: add only evidence-justified features after audits show what is missing.

### 4. Calibration / confidence tasks
Goal: determine whether confidence should be recalibrated, retrained, replaced, or split from current signal scoring.

### 5. Backtest / validation tasks
Goal: prove whether any rebuilt model variant has edge against explicit baselines on trustworthy windows.

### 6. Secondary risk-control follow-ons
Goal: address persistence and containment issues after the model-quality track is framed.
These matter, but they are not the root cause of no edge.

## Ordered manager task sequence

### PHASE A — Data foundation first

#### TASK 1 — MLB_DATA_INVENTORY_AUDIT_001
Type: read-only audit
Track: Track B
Goal:
- inventory all mlb_model season data currently available
- identify existing tables/files, date coverage, schema shape, and obvious gaps
- confirm where shadow recommendation logs and trade outcomes already live
Why first:
- do not backfill blindly until current coverage and storage layout are known

#### TASK 2 — MLB_DATA_GAP_MAP_001
Type: read-only audit
Track: Track B
Depends on: TASK 1
Goal:
- identify what current-season MLB game/team/player/boxscore/state data is missing
- classify must-have vs nice-to-have for model rebuilding
- define exact missing date ranges and entities
Why second:
- turns inventory into an actionable backfill spec instead of a vague data task

#### TASK 3 — MLB_STATS_FOUNDATION_SPEC_001
Type: specification / manager artifact task
Track: Track B
Depends on: TASK 2
Goal:
- define canonical storage location, schema expectations, versioning rules, and feed path into model features
- specify how MLB Stats API data should be normalized and persisted
Why third:
- ensures backfill and updater write into the same durable structure

#### TASK 4 — MLB_CURRENT_SEASON_BACKFILL_BUILD_001
Type: narrow code task
Track: Track B
Depends on: TASK 3
Status: COMPLETE (2026-04-17) — coverage achieved through 2026-04-16
Goal:
- backfill all current-season MLB game stats so far using MLB Stats API
- write into the canonical store only
Why fourth:
- first actual data write, after audits/spec lock the target layout
Completion notes:
- Script written: C:\Users\johnny\Desktop\mlb_model\scripts\backfill_season.py
- Gap dates filled: 2026-04-12 through 2026-04-16 (65 games, 551 pitcher logs, 1178 state rows)
- Prior dates 2026-03-25 through 2026-04-11 confirmed skipped (idempotency working)
- All 6 raw entities + 4 normalized entities written per spec
- Manifest: manifests/backfill_20260417.json

#### TASK 5 — MLB_DAILY_PREV_DAY_UPDATER_BUILD_001
Type: narrow code task
Track: Track B
Depends on: TASK 4
Goal:
- build a daily job that fetches the previous day’s completed MLB games and updates the canonical store
Why fifth:
- keeps the rebuilt dataset current without mixing batch backfill logic into live model logic

#### TASK 6 — MLB_DATA_FOUNDATION_VERIFY_001
Type: read-only verification
Track: Track B
Depends on: TASK 4 and TASK 5
Goal:
- verify date coverage, row counts, schema consistency, and updater correctness
Why sixth:
- prove data foundation before feature/model work begins

### PHASE B — Current model signal audit

#### TASK 7 — MLB_MODEL_INPUT_PATH_AUDIT_001
Type: read-only audit
Track: Track B
Goal:
- identify exactly what features the current model uses end-to-end
- trace whether score, inning, outs, bullpen/pitcher state, and contextual fields actually reach the recommendation layer
Why now:
- root-cause audit before any feature additions

#### TASK 8 — MLB_MARKET_AWARENESS_AUDIT_001
Type: read-only audit
Track: Track B
Depends on: TASK 7
Goal:
- determine whether the current model or post-model signal layer meaningfully uses market price, spread, depth, and near-resolution state
- explain why a 0.01 market could still receive ~55% confidence
Why now:
- isolates model-awareness failure from generic game-state questions

#### TASK 9 — MLB_SIGNAL_FAILURE_CASE_REVIEW_001
Type: read-only audit
Track: Track B
Depends on: TASK 7 and TASK 8
Goal:
- review concrete failure clusters: near-resolved losers, high-confidence stop/gap-stop damage, concentrated slug failures
- map each cluster to missing features, weak model behavior, or downstream execution effects
Why now:
- converts abstract audit findings into concrete failure categories the rebuild must address

### PHASE C — Confidence / calibration

#### TASK 10 — MLB_CONFIDENCE_CALIBRATION_AUDIT_001
Type: read-only audit
Track: Track B
Depends on: TASK 7, TASK 8, TASK 9
Goal:
- determine whether confidence is calibrated, inverted, noisy, or structurally unrelated to outcome quality
- define how confidence should be measured against real outcomes
Why here:
- confidence should be fixed only after signal/input understanding is established

#### TASK 11 — MLB_CONFIDENCE_REDESIGN_SPEC_001
Type: specification / manager artifact task
Track: Track B
Depends on: TASK 10
Goal:
- decide whether confidence should be rescaled, retrained, replaced, or separated from current edge scoring
- define pass/fail calibration metrics
Why here:
- prevents premature code changes before calibration direction is chosen

### PHASE D — Feature engineering and rebuild

#### TASK 12 — MLB_FEATURE_SET_REBUILD_SPEC_001
Type: specification / manager artifact task
Track: Track B
Depends on: TASK 6, TASK 9, TASK 11
Goal:
- define the smallest evidence-justified rebuilt feature set for the next model iteration
- explicitly distinguish required features vs experimental features
Why here:
- feature work should be evidence-driven, not exploratory sprawl

#### TASK 13 — MLB_FEATURE_PIPELINE_BUILD_001
Type: narrow code/data task
Track: Track B
Depends on: TASK 12
Goal:
- implement the rebuilt feature pipeline against the canonical season dataset
Why here:
- first build step after feature spec is stable

#### TASK 14 — MLB_MODEL_RETRAIN_BASELINE_001
Type: narrow model task
Track: Track B
Depends on: TASK 13
Goal:
- retrain a baseline rebuilt model using the new feature pipeline and current-season data
Why here:
- rebuild starts with a baseline model, not immediate optimization

### PHASE E — Validation and edge proof

#### TASK 15 — MLB_BACKTEST_WINDOW_SPEC_001
Type: specification / manager artifact task
Track: Track B
Depends on: TASK 14
Goal:
- define trustworthy historical windows, contamination exclusions, clean-runtime vs broken-runtime segmentation, and benchmark baselines
Why here:
- validation must be locked before comparing models

#### TASK 16 — MLB_BACKTEST_AND_BASELINE_COMPARE_001
Type: read-only / analysis task
Track: Track B
Depends on: TASK 15
Goal:
- compare rebuilt model vs baselines on trustworthy windows
- include random-side, market-price, simple heuristic, and current model baselines where possible
Why here:
- prove whether rebuilt signal exceeds naive alternatives

#### TASK 17 — MLB_EDGE_PROOF_GATE_001
Type: read-only / manager decision audit
Track: Track B
Depends on: TASK 16
Goal:
- apply explicit pass/fail criteria for saying the rebuilt model has edge
- no deployment approval unless criteria pass
Why here:
- formal stop/go gate for model-quality recovery

### PHASE F — Secondary risk-control follow-ons

#### TASK 18 — GAP_STOP_BAN_PERSIST_AUDIT_001
Type: read-only audit
Track: Track A/B boundary but subordinate
Goal:
- verify exact persistence gap for `_session_gap_stop_bans` across restart and define minimal persistence target
Why late:
- useful containment, but not primary cause of no edge

#### TASK 19 — SL_CLUSTER_PERSIST_AUDIT_001
Type: read-only audit
Track: Track A/B boundary but subordinate
Goal:
- verify whether SL cluster state should persist across restart and whether current reset behavior leaks containment
Why late:
- secondary containment follow-on

#### TASK 20 — SESSION_SLUG_CAP_VERIFY_001
Type: read-only verification
Track: Track B containment follow-on
Goal:
- verify whether session slug cap behavior is truly leaking or just unproven in current runtime evidence
Why late:
- containment follow-on only after model-quality framing is established

## Immediate next tasks to open
1. `MLB_DATA_INVENTORY_AUDIT_001`
2. `MLB_DATA_GAP_MAP_001`
3. `MLB_STATS_FOUNDATION_SPEC_001`
4. `MLB_MODEL_INPUT_PATH_AUDIT_001`
5. `MLB_MARKET_AWARENESS_AUDIT_001`

## Why this ordering is correct
- Data foundation comes first because rebuild quality is capped by dataset quality.
- Model audits happen before feature work so missing-context claims are proven, not guessed.
- Confidence redesign waits until signal formation is understood.
- Backtesting and edge proof happen only after rebuilt data + features + model exist.
- Secondary persistence/risk tasks remain explicitly queued, but below the model-quality recovery track because they do not explain no-edge on their own.

## Manager guardrails
- Keep early tasks read-only until root cause is pinned down.
- Do not mix data backfill code with model logic changes in one task.
- Require explicit pass/fail criteria before claiming rebuilt edge.
- Keep paper-only observation mode until validation passes.
