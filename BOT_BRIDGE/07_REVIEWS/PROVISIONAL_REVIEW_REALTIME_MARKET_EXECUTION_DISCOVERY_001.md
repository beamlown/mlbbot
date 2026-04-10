# PROVISIONAL_REVIEW_REALTIME_MARKET_EXECUTION_DISCOVERY_001

Decision: PROVISIONALLY_APPROVED

## Discovery findings

### Reusable Polymarket integration points found
- `core/orderbook.py`
  - existing Polymarket market data integration
  - normalized orderbook snapshot path
  - REST/snapshot based, not websocket streaming
- `core/discovery.py`
  - market discovery / metadata path
- `sports/mlb/adapter.py`
  - MLB-specific market mapping layer
- `core/paper_exec.py` and `core/db.py`
  - local paper execution / persistence, but not Polymarket user-stream integration

### What was not found
- no reusable websocket/client layer for Polymarket market stream
- no reusable websocket/client layer for Polymarket user/order/fill stream

### Can dashboard_server.py host the first realtime slice?
- yes, as the browser-facing SSE host
- but it should consume a dedicated local stream/state source rather than embedding stream-client complexity directly

## Recommendation

New narrow files are justified for implementation:
- `core/market_stream.py`
- `core/state_hub.py`

The recommended first realtime slice is:
- server-side Polymarket market stream for tracked open-position assets only
- keep fallback polling intact
- defer user/fill stream to the next step

## Conclusion

This discovery pass was enough to decide the minimum safe implementation shape. No code changes were made during discovery.
