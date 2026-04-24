# REVIEW_SESSION_PNL_TRUE_START_FIX_001.md

## Verdict
APPROVED

## Decision
Approve `SESSION_PNL_TRUE_START_FIX_001`.

## Why
- Worker stayed within allowed scope.
- Only `bot_core.py` was modified.
- The patch is the correct minimal response to the approved audit finding:
  session PnL was under-counted because `session_start_ts` followed restart timing instead of the intended trading-session start.
- The worker reused the existing startup load block instead of widening scope.
- `python -m py_compile bot_core.py` passed.
- `dashboard_server.py` did not need to change.

## What changed
- `bot_core.py`
- Extended the existing startup restore block to also restore `_session_start_ts` from prior `state.json`
- Restoration is applied when the prior session timestamp is valid and within 24 hours
- This keeps session PnL anchored to the true session start across restarts instead of resetting every time the process restarts

## Runtime note
- Restart is required before this fix is live.
- Per `OPERATOR_ACTION_REQUIRED_001`, stale `__pycache__/bot_core.cpython-*.pyc` must also be deleted before the cold restart or the runtime may still load pre-patch bytecode.

## Manager judgment
Close `SESSION_PNL_TRUE_START_FIX_001` to DONE.
Promote the next queued task:
`POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001`
