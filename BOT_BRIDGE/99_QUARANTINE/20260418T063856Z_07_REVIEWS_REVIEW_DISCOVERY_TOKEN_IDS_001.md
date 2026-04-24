# REVIEW_DISCOVERY_TOKEN_IDS_001

Decision: APPROVED

## What passed
- **Scope**: only `core/discovery.py` modified (cache serializer). ✅
- **Root cause correct**: yes_token_id/no_token_id were parsed into Market dataclass but omitted from the atomic_write_json cache serializer. ✅
- **Fix minimal**: cache writer now includes yes_token_id/no_token_id — nothing else changed. ✅
- **Proof**: refreshed runtime/last_discovery.json contains both token ID fields. ✅
- **Market dataclass/types unchanged**. ✅

## What failed
- None.

## Notes
- This was the prerequisite fix for REALTIME_MARKET_STREAM_DIAG_001 and REALTIME_MARKET_STREAM_TRACKING_FIX_001 — the stream couldn't subscribe to anything because token IDs weren't persisted.

## Next action
- DISCOVERY_TOKEN_IDS_001 → DONE.
