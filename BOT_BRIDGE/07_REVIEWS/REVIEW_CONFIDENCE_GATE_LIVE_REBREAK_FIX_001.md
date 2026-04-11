# REVIEW_CONFIDENCE_GATE_LIVE_REBREAK_FIX_001.md

## Verdict
BLOCKED

## Decision
Do **not** approve `CONFIDENCE_GATE_LIVE_REBREAK_FIX_001` as a code fix.

## Why
- The worker did not make a patch.
- The worker found that the current on-disk `bot_core.py` already contains the expected failed-gate flow:
  - rejection logging
  - `continue`
  - no obvious direct fall-through to `open_position(...)` in the inspected bridge path
- That means the original fix hypothesis in the task brief is no longer safe enough to patch blindly.

## What this means
The live rebreak is still real, but the current brief assumed the bug location incorrectly or too narrowly.

Possible explanations now include:
- the running process is not executing the exact path the worker inspected
- another bridge/open path exists
- duplicate/repeated intents re-enter through a different loop state
- runtime/log evidence is mixing multiple attempts for the same market
- a different call site or helper can still reach `open_position(...)`

## Manager judgment
Open a new expanded-scope read-only trace task:

`CONFIDENCE_GATE_LIVE_REBREAK_TRACE_002`

This task must prove the exact current path that allowed sub-0.60 trades to open, before another code patch is attempted.

## Scope note
- The worker read within the spirit of the task and correctly refused to patch blindly.
- This was the right decision.
- No code was modified.

## Priority
Keep `POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001` queued behind the confidence-gate trace.
The gate issue is still the higher-risk trading problem.
