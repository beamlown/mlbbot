# CLAUDE_TASK_BOARD_UPDATE_SNIPPET.md

Use this to update `08_SHARED_CONTEXT/CLAUDE_TASK_BOARD.md`.

## Header line
Replace the top header note with:

`## Last updated: 2026-04-10 — MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001 reviewed PARTIAL PASS. MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001 opened. 1 ACTIVE task.`

## ACTIVE table row
Replace the current ACTIVE row with:

| task_id | title | priority | subsystem | allowed_files | status |
|---------|-------|----------|-----------|---------------|--------|
| MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001 | Reduce inaccurate rest_fallback usage and preserve live stream mark authority | HIGH | dashboard / live mark pricing | `dashboard_server.py`; `core/state_hub.py` only if strictly needed | ACTIVE — worker-ready. Brief in 05_INBOX. |

## DONE row to add
Add this DONE entry near the top of DONE:

| task_id | title | outcome | allowed_files |
|---------|-------|---------|---------------|
| MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001 | Trace mark-source fallback frequency and guard-message payload origin | PARTIAL PASS 2026-04-10 — mark REST chain traced end-to-end. `rest_fallback` confirmed as expected UI behavior, not a front-end bug. Guard/max-down wording not found in current runtime/dashboard payload. Upstream fallback quality problem remains; follow-on fix opened: MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001. | runtime/state.json, dashboard_server.py, dashboard.html, dashboard.log, bot log (read-only) |

## System-state line to replace
Replace the dashboard display issues line with:

- **Dashboard mark-source issue: FIX TASK OPEN** — MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001 PARTIAL PASS traced the chain. `mark REST` is expected rendering, but fallback appears too frequent/inaccurate for operator trust. `MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001` ACTIVE to restore stream mark authority and harden fallback behavior.

## Keep unchanged for now
- `BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001` is still needed and not yet opened.
- `RUNTIME_USER_STREAM_AUTH_UNBLOCK_001` remains blocked on user credentials.
