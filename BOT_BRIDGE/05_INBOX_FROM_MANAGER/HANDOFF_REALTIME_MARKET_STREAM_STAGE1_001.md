# HANDOFF - REALTIME_MARKET_STREAM_STAGE1_001
## Implement first true Polymarket market-stream-backed pricing path for tracked open positions

Allowed files:
- `C:\Users\johnny\Desktop\sports_bot_v2\core\market_stream.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\core\state_hub.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html` only for tiny wiring enrichment
- BOT_BRIDGE task/result/review files

Token-ID source path:
- open trades from existing DB via `_fetch_trades()`
- local discovery metadata via `DISCOVERY_PATH`
- map open trade `market_slug` / `market_id` to discovered market metadata
- use `yes_token_id` for `BUY_YES`, `no_token_id` for `BUY_NO`

State hub fields introduced:
- `market_slug`
- `market_id`
- `asset_id`
- `current_price`
- `best_bid`
- `best_ask`
- `spread`
- `source_ts`
- `stale`
- `source`

SSE payload after change:
- keeps existing `positions_mark` contract
- enriches each position with:
  - `best_bid`
  - `best_ask`
  - `spread`
  - `source_ts`
  - `mark_source`
- current price / live equity / unrealized now come from stream-backed marks when available

Stream source path:
- `wss://ws-subscriptions-clob.polymarket.com/ws/market`
- subscribe by tracked held-side asset token IDs only
- heartbeat `PING` every 10s

Fallback behavior:
- if stream mark is missing/stale, position is marked stale explicitly
- existing REST/poll snapshot behavior remains intact underneath
- no Odds API involvement in realtime path

Rollback:
- remove market_stream/state_hub integration from `dashboard_server.py`
- remove tiny SSE field enrichment in `dashboard.html`
- fallback polling path remains available
