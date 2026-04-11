# HANDOFF_TP_NEAR_RESOLUTION_CAP_FIX_001.md

## Task
`TP_NEAR_RESOLUTION_CAP_FIX_001`

## Goal
Fix unreachable TP math for near-1.0 entries.

## Why this exists
Tonight's approved audit found that a near-1.0 entry can compute an unreachable TP above 1.0 on a 0-1 contract.
Example from the audit:
- trade #259
- BUY_NO
- entry_px = 0.9447
- computed TP = 1.3226
That TP can never be reached.

## Scope
Primary target:
- `sports_bot_v2/core/risk.py`

Conditionally allowed only if strictly required:
- `.env` only if you must reference an existing near-resolution threshold in a minimal compatible way

Read-only context:
- `logs/bot_baseball_20260410.log`
- `trades_sports.db (SELECT only)`
- `.env`

Do not touch:
- `bot_core.py`
- `dashboard_server.py`
- `dashboard.html`
- `launch_all.py`
- unrelated files

## Required outcome
Implement the smallest safe fix so TP cannot exceed a meaningful upper cap for 0-1 contracts.
Preferred manager direction:
- cap TP at `min(tp_price, NEAR_RESOLUTION_PRICE)` if that fits cleanly in the current architecture.

## Result
Write:
`06_OUTBOX_FROM_WORKER/RESULT_TP_NEAR_RESOLUTION_CAP_FIX_001.json`
