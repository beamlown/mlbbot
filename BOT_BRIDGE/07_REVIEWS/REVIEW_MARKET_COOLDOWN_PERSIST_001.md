# REVIEW_MARKET_COOLDOWN_PERSIST_001.md

## Verdict
APPROVED

## Decision
Approve `MARKET_COOLDOWN_PERSIST_001`.

## Why
- Worker stayed within allowed scope.
- Only `bot_core.py` was modified.
- The patch matches the approved audit finding: `_market_cooldown` was being written only in memory and was wiped on restart.
- The worker added the two required persistence points:
  1. `_write_state()` now includes `market_cooldown_expiry` for non-expired entries
  2. `main()` now restores non-expired cooldowns from prior `state.json` before the first loop
- `python -m py_compile bot_core.py` passed.

## What changed
- `bot_core.py`
- Added `market_cooldown_expiry` to the runtime state payload
- Added startup reload logic to restore active cooldown expiries into `_market_cooldown`

## Runtime note
- Restart is required before this fix is live.
- Per `OPERATOR_ACTION_REQUIRED_001`, stale `__pycache__/bot_core.cpython-*.pyc` must also be deleted before the cold restart or the runtime may still load pre-patch bytecode.

## Manager judgment
Close `MARKET_COOLDOWN_PERSIST_001` to DONE.
Promote the next queued task:
`SESSION_PNL_TRUE_START_FIX_001`
