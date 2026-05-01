# HANDOFF - VERIFY_REALTIME_DASHBOARD_STAGE2_001
## Verify realtime dashboard Stage 2 is truly functioning live

SSE route under verification:
- `GET /api/stream/state`

Pushed payload fields under verification:
- `type`
- `ts`
- `source`
- `stale`
- `open_count`
- `live_equity_total`
- `positions[]` with `market_slug`, `current_price`, `current_price_stale`, `unrealized_pnl_usd`, `live_equity_usd`

For this task, VERIFIED means:
1. the SSE route is actually live on the running server
2. the dashboard can actually consume pushed events
3. at least one visible metric is proven push-driven
4. stale/fresh signaling works from the stream path
5. polling fallback still works
