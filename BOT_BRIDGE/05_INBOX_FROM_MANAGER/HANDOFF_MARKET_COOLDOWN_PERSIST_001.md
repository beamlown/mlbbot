# HANDOFF_MARKET_COOLDOWN_PERSIST_001.md

## Task
`MARKET_COOLDOWN_PERSIST_001`

## Goal
Persist market cooldown across restarts.

## Why this exists
Tonight's approved audit found that `_market_cooldown` is written during the close path but exists only in memory.
A restart wipes it, which allowed markets like CWS-KC to reopen before their intended cooldown expiry.

## Scope
Primary target:
- `sports_bot_v2/bot_core.py`

Conditionally allowed only if strictly required:
- the existing runtime state write/read path if a tiny directly related helper must be touched

Read-only context:
- `logs/bot_baseball_20260410.log`
- `trades_sports.db (SELECT only)`
- `core/risk.py`
- `runtime/state.json`

Do not touch:
- `dashboard_server.py`
- `dashboard.html`
- `.env`
- `launch_all.py`
- unrelated files

## Required outcome
Implement the smallest safe persistence path so cooldown expiry timestamps survive restart and are reloaded on startup.

## Result
Write:
`06_OUTBOX_FROM_WORKER/RESULT_MARKET_COOLDOWN_PERSIST_001.json`
