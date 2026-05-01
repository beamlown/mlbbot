# PROVISIONAL_REVIEW_BASEBALL_POSITION_SEMANTICS_INCIDENT_001

## Status
VERIFIED_CAUSE_FOUND

## Exact affected trades
- `160` / `mlb-mil-bos-2026-04-08` / `BUY_YES`
- `166` / `mlb-sea-tex-2026-04-08` / `BUY_NO`

## Exact current_price source after the fix
`polymarket_stream`, via:
- `dashboard_server._tracked_open_assets()` chooses tracked token id
- `core.market_stream.py` subscribes and updates `GLOBAL_STATE_HUB`
- `dashboard_server._stream_positions_mark()` reads that mark from `GLOBAL_STATE_HUB.snapshot()`

## Exact math after the fix
- `live_equity_usd = qty * current_price`
- `unrealized_pnl_usd = (current_price - entry_px) * qty`

## Exact wrong code path
`dashboard_server.py` in `_stream_positions_mark()` previously had:
- `live_equity_usd = round(qty * current_price, 4)`
- if `BUY_NO`: `unrealized_pnl_usd = round((entry_px - current_price) * qty, 4)`
- else `unrealized_pnl_usd = round((current_price - entry_px) * qty, 4)`

That was the precise BUY_NO sign bug.

## Why this matters
For the live SEA/TEX example, the held NO contract price increased above entry, so equity increased. The old BUY_NO branch still forced unrealized negative, making the card internally false.

## Relation to BOS YES incident
Related, but not identical.
- BOS/MIL exposed held-side semantics confusion around what team YES/NO represented.
- SEA/TEX exposed a hard formula split where dashboard/SSE treated BUY_NO unrealized opposite to its own live equity.

## TP/SL / close monitoring
Yes, broader monitoring paths still inherit semantics risk because execution code still branches on raw BUY_YES/BUY_NO in `core.risk.check_exit()` and `core.paper_exec`.
This patch fixed the proven open-position truth bug in dashboard/SSE math with the smallest safe change in scope.
