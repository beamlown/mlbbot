# REVIEW_PRICE_SOURCE_SINGLE_AUTHORITY_001

Decision: APPROVED

## What passed
- **Scope**: only `dashboard.html` modified — within task goal. ✅
- **Root cause correctly identified**: frontend `buildOpenPaperPositions()` was seeding `current_price: rec?.current_price ?? null` from shadow recommendation context, which competed with stream-backed backend marks. ✅
- **Fix minimal and correct**: changed to `current_price: null` so the live SSE positions_mark payload from `dashboard_server._stream_positions_mark` (backed by `GLOBAL_STATE_HUB` / polymarket_stream) is the sole authority. ✅
- **Source precedence correct after fix**: polymarket_stream mark wins; shadow never overrides live paper card current_price. ✅
- **Live proof**: observed repeated `positions_mark` SSE payloads with stable `mark_source=polymarket_stream` and no flip to a second source. ✅
- **No hard mismatch remaining**: confirmed. ✅
- **Rollback**: revert `dashboard.html` — no server restart needed. ✅

## What failed
- None.

## Notes
- This is a companion fix to BASEBALL_POSITION_SEMANTICS_INCIDENT_001 — together they ensure price truth flows cleanly from stream → backend → SSE → dashboard with no competing frontend writes.

## Next action
- PRICE_SOURCE_SINGLE_AUTHORITY_001 → DONE.
