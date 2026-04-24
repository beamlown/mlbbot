# HANDOFF - VERIFY_REALTIME_MARKET_STREAM_STAGE1_002
## Verify true live Polymarket mark ingress for realtime market stream Stage 1

Exact success condition for Stage 1:
- at least one currently tracked open position must receive a true live Polymarket market mark into runtime state
- that mark must reach `/api/stream/state` with:
  - `mark_source = polymarket_stream`
  - `current_price != null`

Tracked assets expected:
- held-side asset token IDs derived from current open-position slugs (for example current MLB open positions such as `mlb-phi-sf-2026-04-08`, `mlb-hou-col-2026-04-08`, `mlb-bal-cws-2026-04-08` and their mapped token IDs)

Evidence that counts as true live mark ingress:
1. non-empty runtime tracked asset mapping
2. actual websocket subscribe payload with those asset IDs
3. runtime evidence of received market messages
4. state_hub storing parsed mark values
5. SSE showing `mark_source = polymarket_stream` and non-null mark fields for at least one open position
