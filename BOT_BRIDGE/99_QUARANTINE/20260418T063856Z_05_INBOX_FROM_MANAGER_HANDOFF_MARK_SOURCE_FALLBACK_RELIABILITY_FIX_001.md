# HANDOFF_MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001.md

## Task
`MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001`

## Goal
Fix inaccurate / over-frequent fallback pricing on the dashboard.

The `mark REST` chip itself is not the bug.
The upstream trace already proved the chip is rendered correctly.
The real problem is that fallback marks appear to be taking over too often and sometimes feel inaccurate compared with live prices.

## What is already known
- `dashboard_server.py` can write fallback marks via `_poll_stale_mark(...)`
- `dashboard_server.py` later emits `mark_source` into live SSE / positions payload
- `dashboard.html` simply renders what it receives
- Operator reports fallback is too frequent and degrades trust in live card prices

## Your job
Implement the smallest safe fix so:
- live stream marks remain the primary authority when fresh
- `rest_fallback` only takes over when stream marks are truly stale or missing
- the final `mark_source` matches the source actually used

## Scope
Allowed:
- `sports_bot_v2/dashboard_server.py`
- `sports_bot_v2/core/state_hub.py` only if strictly required

Read-only context:
- `runtime/state.json`
- `logs/dashboard.log`
- `dashboard.html`

Do not touch:
- `bot_core.py`
- `.env`
- `core/risk.py`
- `launch_all.py`
- `core/polymarket_stream.py` unless you hit a real blocker and document why manager approval is needed

## Required output
Write:
`06_OUTBOX_FROM_WORKER/RESULT_MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001.json`

Your result must include:
- files read
- files changed
- exact function/section changed
- old behavior vs new behavior
- verification performed
- whether restart is required
