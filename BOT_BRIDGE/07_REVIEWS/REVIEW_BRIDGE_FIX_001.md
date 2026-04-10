# REVIEW_BRIDGE_FIX_001

Decision: APPROVED

## What passed
- Scope: only `bot_core.py` modified (bridge section lines 439–491).
- **Cap check before bridge** (lines 441–446): `_bridge_open_check = fetch_open_trades()` then `if len >= MAX_CONCURRENT_TRADES → BRIDGE SKIP`. Correctly mirrors what `check_entry_gates` does for the native signal loop.
- **Per-intent re-fetch** (line 451): `current_open = fetch_open_trades()` called inside the intent loop before each open. Fresh DB read catches concurrent writes from other processes.
- **Cap check per-intent** (lines 452–457): breaks the intent loop if capacity is reached mid-batch. Prevents a batch of 5 intents from opening positions 4 and 5 after 3 was already opened in the same loop.
- **Race skip** (lines 458–464): re-checks slug against fresh `current_open_slugs`. Logs `BRIDGE RACE SKIP` if another process beat us to the same slug. Correct and distinguishable from the old `[open_position]` gate message.
- All other logic unchanged: `open_position`, `insert_open_trade`, `Signal` construction, `market_lookup` gate, `except` wrapper.
- `ENABLE_MODEL_BRIDGE` is still `False` — worker did not change it. Correct per task instructions.
- Rollback: revert `bot_core.py` only. ✓

## What failed
- none

## Notes
- `fetch_open_trades()` is called up to N+1 times per loop (1 outer + 1 per approved intent). At normal volumes (≤5 intents/loop) this is negligible — it's a local SQLite read.
- Variable name `_bridge_open_check` is slightly unusual but unambiguous.

## Next action
- Update task board: BRIDGE_FIX_001 → DONE, unlock `bot_core.py`.
- With both BRIDGE_FIX_001 and LAUNCH_FIX_001B approved, the bridge re-enable gate is now clear.
