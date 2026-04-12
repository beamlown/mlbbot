# HANDOFF: MLB_PITCHER_BULLPEN_HYDRATION_BUILD_001

## What you are doing
Complete the missing must-have pitcher and bullpen entities in the canonical 2026 MLB foundation.

## Goal
Populate:
- pitcher_game_logs
- bullpen_context

using the existing MLB Stats API source and the already-approved foundation spec, while keeping the corrected completed-season-to-date boundary intact.

## Scope
Stay inside the backfill/hydration path and canonical foundation output only.
Do not start the daily updater. Do not touch model/recommendation code.

## Deliver back
- files changed
- final pitcher_game_logs count
- final bullpen_context count
- final coverage window
- remaining true source-unavailable cases if any

## Do not do
- no storage redesign
- no updater work
- no model work
- no unrelated feature engineering