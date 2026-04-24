# REVIEW_REALTIME_MARKET_STREAM_DIAG_001

Decision: APPROVED

## What passed
- **Scope**: diagnostic only — no code change. ✅
- **VERIFIED_CAUSE_FOUND**: _tracked_open_assets() returned {} because discovery cache didn't contain token IDs for open-position markets. ✅
- **Evidence chain complete**: tracked_assets was empty → websocket subscribed to nothing → state_hub got no marks → SSE showed poll_fallback marks. ✅
- **After discovery refresh**: token IDs present, tracked assets non-empty. ✅
- **Next action correctly identified**: refresh discovery cache + restart dashboard server. ✅

## What failed
- None.

## Next action
- REALTIME_MARKET_STREAM_DIAG_001 → DONE.
