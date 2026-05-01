# HANDOFF_SESSION_PNL_TRUE_START_FIX_001.md

## Task
`SESSION_PNL_TRUE_START_FIX_001`

## Goal
Track true session PnL from the actual session start, not simply the last restart.

## Why this exists
Tonight's approved audit found that the dashboard/session view under-counts losses because `session_start_ts` follows restart timing rather than the actual beginning of tonight's trading session.

## Scope
Primary targets:
- `sports_bot_v2/bot_core.py`
- `sports_bot_v2/dashboard_server.py`

Conditionally allowed only if strictly required:
- the existing runtime state path through current code

Read-only context:
- `logs/bot_baseball_20260410.log`
- `runtime/state.json`
- `trades_sports.db (SELECT only)`

Do not touch:
- `core/risk.py`
- `dashboard.html`
- `.env`
- `launch_all.py`
- unrelated files

## Required outcome
Implement the smallest safe change so session PnL reflects the intended trading session start rather than just the most recent restart.

## Result
Write:
`06_OUTBOX_FROM_WORKER/RESULT_SESSION_PNL_TRUE_START_FIX_001.json`
