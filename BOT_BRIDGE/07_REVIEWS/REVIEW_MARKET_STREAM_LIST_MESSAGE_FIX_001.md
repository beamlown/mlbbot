# REVIEW_MARKET_STREAM_LIST_MESSAGE_FIX_001

Decision: APPROVED

## What passed
- **Scope**: only `core/market_stream.py` modified (_on_message parser). ✅
- **Root cause fixed**: parser previously assumed dict payload and called data.get(); live stream sends list-shaped messages, causing crash. ✅
- **Fix correct**: _on_message now normalizes payloads to list of items, processes dict items only, handles both shapes safely. ✅
- **VERIFIED**: after fix — mark_count_received=1, parser_hit_count=1, last_message_type="book", last_state_hub_update_slug="mlb-phi-sf-2026-04-08", last_error=null. ✅
- **Chain complete**: websocket → parser → state_hub update now all functional. ✅
- **No strategy/execution logic changed**. ✅

## What failed
- None.

## Notes
- This was the final fix that unblocked VERIFY_REALTIME_MARKET_STREAM_STAGE1_FINAL.

## Next action
- MARKET_STREAM_LIST_MESSAGE_FIX_001 → DONE.
