# PROVISIONAL_REVIEW_DUPLICATE_ENTRY_LIVE_REAUDIT_001

Decision: PROVISIONALLY_APPROVED

## What was verified

- **Exact live DB path**: `C:\Users\johnny\Desktop\sports_bot_v2\trades_sports.db`
- **Unique open-slug index exists**: yes
  - `idx_trades_one_open_per_slug`
  - SQL: `CREATE UNIQUE INDEX idx_trades_one_open_per_slug ON trades(market_slug) WHERE status='open'`
- **Current duplicate open rows**: 0
- **Current open row count**: 3
- **Capacity status**: within configured limit
  - `.env`: `MAX_CONCURRENT_TRADES=3`
  - `runtime/state.json`: `slots.open=3`, `slots.max=3`
  - live DB query: 3 open rows

## Stack-path proof

- `core/db.py` still contains the protected insert path:
  - `BEGIN IMMEDIATE`
  - pre-insert `SELECT id FROM trades WHERE market_slug=? AND status='open' LIMIT 1`
  - `sqlite3.IntegrityError` guard on insert
- `bot_core.py` still uses `insert_open_trade()` in both:
  - the main bot open flow
  - the model bridge open flow
- No alternate insert bypass was found in the inspected runtime path.

## Log-window proof

- Recent logs show repeated `BRIDGE SKIP - at capacity (3/3)` messages, not uncontrolled additional opens.
- In the inspected fresh window, one position closed and then one different-slug position opened.
- No evidence was found of two fresh open events creating duplicate live rows for the same `market_slug`.

## Conclusion

`DUPLICATE_ENTRY_LIVE_REAUDIT_001` is **VERIFIED** based on live DB schema proof, current row-state proof, runtime-path proof, and recent log behavior.
