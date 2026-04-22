# PROVISIONAL_REVIEW_LIVE_CARD_PNL_SIGN_REGRESSION_001

## Status
PARTIAL

## What was verified
- `localhost:8900` is actively listening on PID `35892`.
- Listener owner resolves to `python.exe` running `dashboard_server.py`.
- `http://localhost:8900/api/state` returned HTTP 200.
- `http://localhost:8900/api/stream/state` returned HTTP 200 and streamed `event: positions_mark` data.

## Before/after proof summary
- Before: prior task state said `/api/stream/state` hung with no response, blocking verification.
- After: a direct Python probe returned `200` and readable SSE content beginning with `event: positions_mark`.

## Restart/activation
- No restart or activation was required during this verification pass.

## Remaining gap
- This pass cleared the runtime-availability blocker, but did not complete the specific unrealized PnL sign re-verification against live held-contract math.

## Exact artifact paths
- Result: `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_LIVE_CARD_PNL_SIGN_REGRESSION_001.json`
- Review: `C:\Users\johnny\Desktop\BOT_BRIDGE\07_REVIEWS\PROVISIONAL_REVIEW_LIVE_CARD_PNL_SIGN_REGRESSION_001.md`
