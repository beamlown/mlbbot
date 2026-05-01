# HANDOFF - REALTIME_MARKET_STREAM_DIAG_001
## Diagnose missing live Polymarket mark ingress in Stage 1 runtime path

Exact live blocker under diagnosis:
- upgraded SSE path is live
- stream-shaped fields are present
- but positions still show `mark_source: poll_fallback` and null mark values
- so true Polymarket marks are not entering runtime state

Runtime path inspected:
1. open trades from `_fetch_trades()`
2. token-ID mapping via `_tracked_open_assets()` using `runtime/last_discovery.json`
3. websocket subscribe payload construction in `core/market_stream.py`
4. runtime message/state path into `core/state_hub.py`
5. live SSE output from `/api/stream/state`

Expected diagnostic outcomes:
- wrong token mapping
- wrong subscribe payload
- wrong event parsing
- no events in current window
- or another concrete runtime cause
