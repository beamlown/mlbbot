# HANDOFF - MARKET_STREAM_LIST_MESSAGE_FIX_001
## Handle list-shaped Polymarket market stream messages in Stage 1 parser

Exact parser failure before fix:
- live market stream messages were arriving
- parser assumed dict-shaped payloads and called `.get(...)`
- at least some real incoming payloads were list-shaped
- runtime error: `'list' object has no attribute 'get'`

Observed/expected message shapes:
- single dict event payloads
- list/batch payloads containing multiple dict event items

Minimal parser fix applied:
- normalize incoming payloads to `items = data if isinstance(data, list) else [data]`
- iterate only dict items
- ignore non-dict items safely
- keep extraction limited to Stage 1 fields only:
  - asset identity
  - current price
  - best bid
  - best ask
  - spread
  - mark/source timing

Rollback:
- revert the narrow list/dict normalization change in `core/market_stream.py`
