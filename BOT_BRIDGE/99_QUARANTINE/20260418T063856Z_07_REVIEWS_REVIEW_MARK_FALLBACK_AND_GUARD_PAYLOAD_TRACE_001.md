# REVIEW_MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001.md

## Verdict
PARTIAL PASS

## Decision
Close `MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001` to DONE and open a new fix task:
`MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001`.

## What was confirmed
- `mark REST` is expected UI behavior when the live positions payload carries `mark_source="rest_fallback"`.
- The mark-source chain is now clear:
  1. `dashboard_server.py` `_poll_stale_mark(...)` can write fallback marks with `source='rest_fallback'`
  2. `dashboard_server.py` `_stream_positions_mark()` maps mark `source` into the live positions payload field `mark_source`
  3. `dashboard.html` renders `rest_fallback -> "mark REST"` and `poll_fallback -> "mark POLL"`
- The dashboard layer is not synthesizing a hardcoded `"max down"` warning.
- Current runtime truth had no active `last_guard_result`, `guard`, `last_guard_reason`, or `last_guard_reasons` payload at audit time.

## Why this is only a PARTIAL PASS
The trace did not prove a front-end bug. It did prove the upstream source chain, but two operational gaps remain:

1. **Fallback mark quality / frequency**
   - The operator reports fallback marks are inaccurate and are visible more often than true live market prices.
   - The trace confirms fallback is active in-session.
   - The current evidence supports a real upstream pricing/freshness problem or an overly eager fallback path, not a dashboard rendering bug.

2. **Guard warning mismatch**
   - No current runtime/dashboard payload source for the `"max down"` style warning was found in the audited snapshot.
   - If that warning recurs, the exact payload must be captured live at the moment it appears.
   - This remains unresolved, but it is secondary to the mark-source reliability issue.

## Manager judgment
The next highest-value task is **not** another dashboard.html audit.
It is a surgical fix task to restore live stream marks as the primary authority and reduce inaccurate `rest_fallback` dominance.

## New task opened
`MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001`

## Scope guidance
- Primary target: `sports_bot_v2/dashboard_server.py`
- Secondary file only if strictly required: `sports_bot_v2/core/state_hub.py`
- Do not widen into a broad stream refactor unless the minimal patch cannot solve fallback dominance safely.

## Follow-on note
The guard-warning issue should remain deferred unless it reproduces again with capturable live payload evidence.
