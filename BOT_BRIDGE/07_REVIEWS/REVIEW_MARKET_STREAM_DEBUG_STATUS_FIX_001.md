# REVIEW_MARKET_STREAM_DEBUG_STATUS_FIX_001

Decision: APPROVED

## What passed
- **Scope**: only `core/market_stream.py` modified (indentation fix). ✅
- **Root cause found**: debug_status() was indented under _to_float() instead of MarketStreamClient — method didn't exist on the object, crashing the handler. ✅
- **Fix minimal**: correct indentation only. ✅
- **Debug status now works**: thread alive, connected=true, tracked_asset_count=3, subscribe payload present, last_message_ts present. ✅
- **Parser error exposed**: "list' object has no attribute 'get'" — stream receives list-shaped messages, not dict. Correctly surfaced. ✅
- **Rollback**: revert market_stream.py. ✅

## Notes
- This diagnostic step revealed the parser shape mismatch, which MARKET_STREAM_LIST_MESSAGE_FIX_001 resolved.

## Next action
- MARKET_STREAM_DEBUG_STATUS_FIX_001 → DONE.
