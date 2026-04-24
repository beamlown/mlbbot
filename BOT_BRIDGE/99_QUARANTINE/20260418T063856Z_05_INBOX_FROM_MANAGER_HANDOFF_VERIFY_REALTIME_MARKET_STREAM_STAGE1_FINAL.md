# HANDOFF - VERIFY_REALTIME_MARKET_STREAM_STAGE1_FINAL
## Final end-to-end verification of realtime Polymarket market stream Stage 1

Exact final success condition for Stage 1:
- `/api/stream/state` must show at least one tracked open position with:
  - `mark_source = polymarket_stream`
  - non-null `current_price`
- proving websocket -> parser -> state_hub -> SSE end-to-end flow

What counts as end-to-end proof:
1. live SSE payload with `mark_source = polymarket_stream`
2. non-null stream-backed price for at least one tracked position
3. derived `unrealized_pnl_usd` / `live_equity_usd` present from that stream-backed price
4. fallback still remains available for stale/missing stream marks
