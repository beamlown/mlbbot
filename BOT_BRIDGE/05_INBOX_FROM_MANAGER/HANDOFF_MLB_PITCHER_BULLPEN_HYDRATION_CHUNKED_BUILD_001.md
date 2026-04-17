# HANDOFF: MLB_PITCHER_BULLPEN_HYDRATION_CHUNKED_BUILD_001

## What you are doing
Complete pitcher_game_logs and bullpen_context hydration using a chunked or resumable approach.

## Goal
Finish the missing must-have entities in the canonical 2026 foundation without full-run termination.

## Scope
- same canonical foundation target
- same completed-season-to-date boundary
- no updater work
- no model work
- no schema redesign unless a tiny compatible change is strictly required for chunk-safety

## Deliver back
- files changed
- final trustworthy pitcher_game_logs count
- final trustworthy bullpen_context count
- completed-season boundary
- chunk/resume behavior
- any remaining true source-unavailable cases

## Do not do
- no updater activation
- no model/recommendation changes
- no unrelated data tasks
- no broad repo sweep