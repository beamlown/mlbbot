# HANDOFF - REALTIME_MARKET_EXECUTION_DISCOVERY_001
## Discovery pass for Polymarket realtime market/user execution integration

Discovery only. No code changes.

Allowed discovery files:
- `dashboard_server.py`
- `dashboard.html`
- `launch_all.py`
- any existing Polymarket-related client/integration files already inside `sports_bot_v2`
- BOT_BRIDGE task/result/review files

Allowed future new files only if discovery proves necessary:
- `core/state_hub.py`
- `core/market_stream.py`
- `core/user_stream.py`

What to determine:
1. exact existing files that already handle Polymarket market data
2. exact existing files that already handle Polymarket user/order/fill data
3. whether there is already a reusable websocket/client layer
4. whether `dashboard_server.py` can host the first realtime slice cleanly
5. the smallest safe implementation plan
