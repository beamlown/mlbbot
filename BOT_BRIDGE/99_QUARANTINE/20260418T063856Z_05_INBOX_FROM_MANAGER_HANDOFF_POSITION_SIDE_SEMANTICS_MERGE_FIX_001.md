# HANDOFF_POSITION_SIDE_SEMANTICS_MERGE_FIX_001.md

## Task
`POSITION_SIDE_SEMANTICS_MERGE_FIX_001`

## Goal
Fix the client-side merge bug that lets stale cached mark data overwrite the current trade's backed-team / side semantics.

## Why this exists
The approved audit found:
- execution truth is clean
- dashboard_server payload mapping is clean
- the bug is in `dashboard.html`
- `renderUnifiedPositions()` currently does a full-object spread merge from `markMap`, which lets stale fields from an older trade on the same slug overwrite the current trade's correct `side`, `backed_team`, and `faded_team`
- a secondary Games-tab slug-key mismatch was also found in the same file

## Scope
Primary target:
- `sports_bot_v2/dashboard.html`

Read-only context:
- `dashboard_server.py`
- `runtime/state.json`
- `logs/dashboard.log`

Do not touch:
- `bot_core.py`
- `core/risk.py`
- `.env`
- `launch_all.py`
- unrelated files

## Required outcome
Implement the smallest safe dashboard.html-only patch so stale cache merge data cannot overwrite semantic identity fields.
If safe in the same file, also fix the Games-tab slug key mismatch.

## Result
Write:
`06_OUTBOX_FROM_WORKER/RESULT_POSITION_SIDE_SEMANTICS_MERGE_FIX_001.json`
