# HANDOFF_BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001.md

## Task
`BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001`

## Goal
Prevent duplicate or repeated intents for the same slug from bypassing gate protections inside a single bridge loop.

## Why this exists
Prior approved audits found that repeated intents for the same slug could still get through after one instance was already rejected.
With the core risk.py fixes now staged, the next critical bridge-side fix is to ensure a slug rejected once in a loop iteration cannot still open later in that same iteration.

## Scope
Primary target:
- `sports_bot_v2/bot_core.py`

Conditionally allowed only if strictly required:
- `sports_bot_v2/core/model_bridge.py`

Read-only context:
- `logs/bot_baseball_20260410.log`
- `trades_sports.db (SELECT only)`
- `core/risk.py`

Do not touch:
- `dashboard_server.py`
- `dashboard.html`
- `.env`
- `launch_all.py`
- unrelated files

## Required outcome
Implement the smallest safe protection so repeated intents for the same slug cannot bypass the bridge gate logic within one loop.

## Result
Write:
`06_OUTBOX_FROM_WORKER/RESULT_BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001.json`
