# HANDOFF_CONFIDENCE_GATE_LIVE_REBREAK_001.md

## Task
`CONFIDENCE_GATE_LIVE_REBREAK_001`

## Goal
Find out why the bot is still opening ~30–40% confidence trades after the latest restart.

## Read-only only
Do not modify code.
Do not restart processes.
Do not widen scope.

## What is already known
- The 0.60 floor was added in `risk.py`
- The bridge path was patched to call `check_entry_gates()`
- Previous postfix verify only partially passed
- Current runtime now shows new open trades with confidence:
  - 241 = 0.3863
  - 243 = 0.3279
  - 244 = 0.3769

## Your job
Use logs, current runtime state, current code, .env, and DB read-only evidence to explain the exact live bypass or mismatch that still exists now.

## Result
Write:
`06_OUTBOX_FROM_WORKER/RESULT_CONFIDENCE_GATE_LIVE_REBREAK_001.json`
