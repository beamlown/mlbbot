# HANDOFF_CONFIDENCE_GATE_LIVE_REBREAK_TRACE_002.md

## Task
`CONFIDENCE_GATE_LIVE_REBREAK_TRACE_002`

## Goal
Prove the exact current live path that allowed sub-0.60 trades to open.

## Why this exists
The previous fix task was blocked for the right reason:
the current on-disk `bot_core.py` already appears to reject and continue on failed gate checks in the inspected bridge path, so a blind patch would be unsafe.

## Read-only only
Do not modify code.
Do not restart processes.
Do not widen scope unless you discover another concrete open_position path and document why you needed to read that file.

## Core question
How did trades 241 / 243 / 244 still open below 0.60?

## Required approach
- trace logs around those exact trades
- inspect current open_position call paths for bridge entries
- determine whether the issue is:
  - another open path
  - duplicate/repeated intents
  - loop re-entry
  - runtime divergence from on-disk code
  - or another concrete cause

## Result
Write:
`06_OUTBOX_FROM_WORKER/RESULT_CONFIDENCE_GATE_LIVE_REBREAK_TRACE_002.json`
