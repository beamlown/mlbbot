# REVIEW_RESOLUTION_WATCHER_INTEGRATE_001

Decision: APPROVED

## What passed
- Scope respected: only `bot_core.py` code changes for the implementation task.
- Added `_load_resolved_markets()` cache with mtime-based reload behavior.
- Exit loop now checks resolved-market state before `check_exit()` and force-closes with resolution pricing.
- `market_resolved` exits update close records and stats without adding cooldown.
- `python -m py_compile bot_core.py` passed.

## What failed
- none

## Notes
- A temporary smoke-test `runtime/resolved_markets.json` was created and then removed after successful loader validation.

## Next action
- Move task to approved/done flow.
