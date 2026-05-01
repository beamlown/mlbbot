# PROVISIONAL_REVIEW_STALE_MARK_REST_FALLBACK_001

## Decision
IMPLEMENTED_PENDING_OPERATOR_RESTART

## Scope compliance
- Changed **only** `dashboard_server.py`.
- No edits to `market_stream.py`, `state_hub.py`, or any other production file.
- No process restart was performed in this pass.

## What changed
1. Added module-level REST fallback config and throttle state:
   - `CLOB_BOOK`
   - `STALE_REST_POLL_SEC`
   - `STALE_REST_THROTTLE_SEC`
   - `_rest_poll_ts`
   - `_rest_poll_lock`

2. Added `_poll_stale_mark(slug, market_id, asset_id)` before `_stream_positions_mark()`.
   - Fetches Polymarket CLOB book by token id.
   - Derives `best_bid`, `best_ask`, `current_price`, and `spread`.
   - Injects fresh mark data into `GLOBAL_STATE_HUB.update_mark(..., source='rest_fallback')`.

3. Inserted inline stale-mark fallback block in `_stream_positions_mark()` between:
   - `marks = GLOBAL_STATE_HUB.snapshot(stale_after_sec=15.0)`
   - `trades = _fetch_trades(limit=100)`

## Static verification
- Module-level additions present at lines 57-61.
- `_poll_stale_mark()` begins at line 394.
- REST fallback block is present starting after the snapshot call and before trade fetch.
- `python -m py_compile C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py` succeeded.

## Runtime verification status
Not completed in this pass.
Reason: task explicitly forbids restarting the process, and the active runtime must be restarted by the operator before `[STALE_POLL]` logs, `mark_source='rest_fallback'`, and stale-to-fresh behavior can be observed.

## Artifact paths
- Result: `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_STALE_MARK_REST_FALLBACK_001.json`
- Review: `C:\Users\johnny\Desktop\BOT_BRIDGE\07_REVIEWS\PROVISIONAL_REVIEW_STALE_MARK_REST_FALLBACK_001.md`
