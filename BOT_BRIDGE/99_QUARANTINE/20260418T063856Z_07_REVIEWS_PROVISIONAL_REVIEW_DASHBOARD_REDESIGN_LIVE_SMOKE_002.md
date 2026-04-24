# PROVISIONAL_REVIEW_DASHBOARD_REDESIGN_LIVE_SMOKE_002

## Verdict
PARTIAL

## Passed
- `http://localhost:8900/` returned HTTP 200.
- `http://localhost:8900/api/state` returned HTTP 200.
- `/api/state` included `bankroll`, `rolling.r25.win_rate`, and `bridge_enabled`.
- `http://localhost:8900/api/trades?limit=60` returned HTTP 200.
- Open trade TP/SL semantics were correct for the current `BUY_NO` position.
- `http://localhost:8900/api/stream/state` returned HTTP 200 and streamed `positions_mark` events.
- Tabs present in served HTML: LIVE, POSITIONS, GAMES, HISTORY, SYSTEM.
- Advisory label present in GAMES tab HTML: `Shadow Advisory - Not Executed`.

## Not fully passed
1. **SSE sign verification could not be completed**
   - The live SSE sample showed one open `BUY_NO` position (`mlb-ari-nym-2026-04-09`) with `current_price = null`, `live_equity_usd = null`, and `unrealized_pnl_usd = null`.
   - Because the mark was stale/null, the required formula check `unrealized_pnl_usd = (current_price - entry_px) * qty` could not be exercised on a non-null live price in this pass.

2. **Shadow absent from LIVE tab failed**
   - Served dashboard HTML still contains `id="shadow-feed"`.
   - That means the acceptance criterion `#shadow-feed not in tab-live HTML` was not satisfied on this snapshot.

## Exact artifact path
- Result: `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_DASHBOARD_REDESIGN_LIVE_SMOKE_002.json`
- Review: `C:\Users\johnny\Desktop\BOT_BRIDGE\07_REVIEWS\PROVISIONAL_REVIEW_DASHBOARD_REDESIGN_LIVE_SMOKE_002.md`
