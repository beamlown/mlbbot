# HANDOFF_MARK_SOURCE_FALLBACK_RELIABILITY_VERIFY_001.md

## Task
`MARK_SOURCE_FALLBACK_RELIABILITY_VERIFY_001`

## Goal
Verify that the fallback reliability fix is live and that stream marks now remain primary when healthy.

## Read-only only
Do not modify code.
Do not restart processes.
Do not widen scope.

## Check
1. restart evidence for dashboard process
2. dashboard log behavior after restart
3. whether healthy stream marks keep authority
4. whether `mark REST` now appears only for true stale/missing cases
5. whether fallback frequency is materially reduced

## Files
- `sports_bot_v2/logs/dashboard.log`
- `sports_bot_v2/runtime/state.json`
- `sports_bot_v2/dashboard_server.py` (read-only if needed for framing only)

## Result
Write:
`06_OUTBOX_FROM_WORKER/RESULT_MARK_SOURCE_FALLBACK_RELIABILITY_VERIFY_001.json`
