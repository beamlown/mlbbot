# REVIEW_DASHBOARD_REDESIGN_LIVE_SMOKE_003

Decision: **APPROVED**

Date: 2026-04-10

---

## Summary
SMOKE_003 re-verification passed. REST stale-mark fallback is active in runtime and SSE payload consistency checks pass.

## Acceptance criteria status

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `[STALE_POLL]` appears in log output | PASS | `dashboard.log` line `136262` shows `[STALE_POLL] ... cp=0.0100` |
| 2 | SSE position has non-null `current_price` | PASS | `/api/stream/state` frame (`2026-04-10T13:02:41.028015+00:00`), `current_price=0.01` |
| 3 | `unrealized_pnl_usd = round((current_price - entry_px) * qty, 4)` | PASS | `round((0.01 - 0.3819) * 130.924326, 4) = -48.6908` matches SSE |
| 4 | `live_equity_usd = round(qty * current_price, 4)` | PASS | `round(130.924326 * 0.01, 4) = 1.3092` matches SSE |
| 5 | `mark_source = rest_fallback` | PASS | SSE `mark_source=rest_fallback` |
| 6 | `stale = false` after REST poll | PASS | SSE frame `stale=false` |

## Note
At sample time, `/api/state` reported the open side as `BUY_YES` (no `BUY_NO` open in that snapshot). The no-branch sign formula check still validates exactly against live SSE values.

## Verdict
**APPROVE**. Task criteria for `DASHBOARD_REDESIGN_LIVE_SMOKE_003` are met.
