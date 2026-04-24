# REVIEW_MARK_SOURCE_FALLBACK_RELIABILITY_VERIFY_001.md

## Verdict
PROVISIONAL PASS

## Decision
Close `MARK_SOURCE_FALLBACK_RELIABILITY_VERIFY_001` to DONE.

## What was confirmed
- Worker stayed read-only. No files changed. Scope respected.
- Five live SSE frames sampled from `/api/stream/state` with 3 open positions active.
- Fresh healthy markets carried `mark_source='polymarket_stream'` across multiple frames — primary protection of the fix is confirmed working.
- REST fallback did NOT replace a fresh stream mark in any sampled frame — consistent with the patch gate logic.
- One market exhibited `current_price_stale=true` independently (upstream stream freshness degraded for that slug), while unaffected markets retained stream-driven values. This is expected edge behavior, not a regression.

## Why PROVISIONAL and not full PASS
1. **Fallback path not live-fired**: No `rest_fallback` event was observed during the verification window. The rule "fallback only when stale/missing" is confirmed by code review (`_has_fresh_stream_mark` guard at line 455) but not by observing a fallback triggering correctly in the healthy → stale → recover sequence.
2. **Short window**: 5 frames is enough to confirm the healthy-path, not enough to conclusively rule out edge-case fallback dominance under slower stream recovery scenarios.

## Code evidence reviewed
- `dashboard_server.py` line ~447–455: `_has_fresh_stream_mark` guard is correctly written. Condition requires `current_price is not None`, `source == "polymarket_stream"`, `_mark_age <= STALE_REST_POLL_SEC`, and `not stale`. Only all four passing blocks REST polling. Logic is sound.
- No regression in mark_source labeling — `mark_source` accurately reflects the source used.

## Process note
The VERIFY brief (TASK_MARK_SOURCE_FALLBACK_RELIABILITY_VERIFY_001.json) stated `depends_on: MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001 (APPROVED)`. This implies the FIX was expected to be manager-approved before VERIFY ran. The FIX review (APPROVED) existed in 07_REVIEWS when VERIFY was executed — dependency was technically satisfied even though the board wasn't updated. No harmful work was done.

## Runtime note
- Worker noted restart was not required for the verify itself.
- Prior REVIEW_MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001 confirmed dashboard restart was completed after the fix.

## Remaining open items
- "max down" style guard warning: deferred — no current runtime guard payload; capture live at next occurrence.
- Longer-window fallback frequency observation remains available if operator reports recurring `mark REST` dominance after this patch.
