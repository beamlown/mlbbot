# PROVISIONAL_REVIEW_PRICE_SOURCE_SINGLE_AUTHORITY_001

Decision: PROVISIONALLY_APPROVED

## Exact paths found writing current_price
- `sports_bot_v2\core\market_stream.py` -> websocket updates into `GLOBAL_STATE_HUB.update_mark(...)`
- `sports_bot_v2\core\state_hub.py` -> mark ownership storage/snapshot
- `sports_bot_v2\dashboard_server.py` -> SSE positions payload surface
- `sports_bot_v2\dashboard.html` -> `buildOpenPaperPositions(...)` previously seeded `current_price` from `rec?.current_price`

## Confirmed bug
- live paper card `current_price` did not have single authority because shadow recommendation context could seed frontend price before/alongside stream-backed payloads

## Fix accepted
- removed shadow as a live paper card `current_price` writer
- fresh `polymarket_stream` mark now wins by rule
- fallback is reserved for missing/stale stream situations

## One live proof sample
- `/api/stream/state` produced repeated `positions_mark` events with stable `mark_source=polymarket_stream`

## Conclusion
Status can be treated as `VERIFIED` for the narrow price-authority fix.
