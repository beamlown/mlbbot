# REVIEW_DUPLICATE_ENTRY_FIX_001

Decision: APPROVED

## What passed
- **Scope**: only `core/db.py` and `bot_core.py` modified — matches allowed_files exactly. ✅
- **UNIQUE partial index**: `idx_trades_one_open_per_slug ON trades(market_slug) WHERE status='open'` added in `init_db()` with try/except wrapper. Correctly handles existing duplicate rows (logs warning, skips). ✅
- **BEGIN IMMEDIATE**: `insert_open_trade()` opens an exclusive write lock at transaction start via `conn.execute("BEGIN IMMEDIATE")`, making the check-and-insert atomic across concurrent processes. ✅
- **Pre-check SELECT**: existing open slug is checked before insert; on match, rolls back and returns `None`. ✅
- **IntegrityError catch**: secondary safety net via `sqlite3.IntegrityError` at the INSERT level also returns `None`. ✅
- **Return type**: changed from `int` to `int | None` — callers now receive `None` on duplicate. ✅
- **Native loop (bot_core.py)**: `if trade_id is None: logger.info("OPEN SKIPPED..."); continue` correctly prevents open_count increment on duplicate. ✅
- **Bridge section (bot_core.py)**: same `if trade_id is None` guard with `BRIDGE OPEN SKIPPED (duplicate slug)` log and `continue`. ✅
- **Rollback possible**: revert both files; UNIQUE INDEX harmless to leave in DB. ✅
- **No disallowed files modified**. ✅

## What failed
- None.

## Notes
- The dual defense (BEGIN IMMEDIATE + UNIQUE index) is the correct layered approach. Even if the UNIQUE index fails to create due to pre-existing duplicates, the BEGIN IMMEDIATE check still prevents new duplicates.
- Existing duplicate trades in the DB are not remediated by this fix — they remain. A separate incident task (INCIDENT_PROCESS_DB_001) presumably handles that cleanup.

## Next action
- DUPLICATE_ENTRY_FIX_001 → DONE.
- Per task board: post-fix relaunch sequence should be executed by user: stop all bot_core processes, clear PID, restart.
