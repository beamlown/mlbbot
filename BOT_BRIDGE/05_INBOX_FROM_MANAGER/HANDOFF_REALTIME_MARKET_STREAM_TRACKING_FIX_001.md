# HANDOFF - REALTIME_MARKET_STREAM_TRACKING_FIX_001
## Make tracked-asset market-stream subscription recover when discovery/token mapping becomes available

Exact blocker in one sentence:
- the runtime could get stuck with open positions but an empty tracked-asset map, so the market websocket subscribed to nothing and never recovered automatically.

Runtime path changed:
- `dashboard_server.py`
  - recompute tracked assets
  - trigger safe discovery refresh when open positions exist but tracked assets are empty
- `core/market_stream.py`
  - resubscribe by closing/restarting websocket when tracked asset set changes

Minimum safe fix:
- detect `open_positions && tracked_assets == {}`
- refresh discovery cache safely
- recompute tracked assets
- update stream tracked asset set
- if tracked asset set changed, force websocket reconnect so new subscription payload is sent

Rollback:
- revert the narrow recompute/resubscribe changes in `dashboard_server.py` and `core/market_stream.py`
