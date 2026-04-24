# HANDOFF_CONFIDENCE_GATE_LIVE_REBREAK_FIX_001.md

## Task
`CONFIDENCE_GATE_LIVE_REBREAK_FIX_001`

## Goal
Fix the current live confidence-gate rebreak so sub-0.60 signals cannot open after gate rejection.

## What is already known
- The current runtime still opened new live trades below 0.60.
- The same system also emitted `confidence_too_low:...:0.600` reject evidence.
- Therefore this is not simple config drift; it is a live gate/open ordering inconsistency or bypass.

## Scope
Primary target:
- `sports_bot_v2/bot_core.py`

Conditionally allowed only if strictly required:
- `sports_bot_v2/core/model_bridge.py`
- `sports_bot_v2/core/risk.py` (prefer read-only unless truly necessary)

Read-only context:
- `logs/bot_baseball_20260410.log`
- `.env`
- `trades_sports.db (SELECT only)`

Do not touch:
- `dashboard_server.py`
- `dashboard.html`
- `launch_all.py`
- unrelated files

## Required outcome
Implement the smallest safe patch so a signal rejected by `check_entry_gates()` cannot still reach `open_position()` through the current live bridge flow.

## Result
Write:
`06_OUTBOX_FROM_WORKER/RESULT_CONFIDENCE_GATE_LIVE_REBREAK_FIX_001.json`
