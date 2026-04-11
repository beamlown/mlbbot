# CLAUDE_TASK_BOARD_UPDATE_SNIPPET.md

Use this to update `08_SHARED_CONTEXT/CLAUDE_TASK_BOARD.md`.

## Header line
Replace the top header note with:

`## Last updated: 2026-04-10 — MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001 approved. MARK_SOURCE_FALLBACK_RELIABILITY_VERIFY_001 opened. 1 ACTIVE task.`

## ACTIVE table row
Replace the current ACTIVE row with:

| task_id | title | priority | subsystem | allowed_files | status |
|---------|-------|----------|-----------|---------------|--------|
| MARK_SOURCE_FALLBACK_RELIABILITY_VERIFY_001 | Verify live stream mark authority after fallback reliability fix | HIGH | read-only runtime verification — dashboard / live mark pricing | `logs/dashboard.log`, `runtime/state.json`, `dashboard_server.py` | ACTIVE — awaiting worker execution after restart. Brief in 05_INBOX. |

## DONE row to add
Add this DONE entry near the top of DONE:

| task_id | title | outcome | allowed_files |
|---------|-------|---------|---------------|
| MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001 | Reduce inaccurate rest_fallback usage and preserve live stream mark authority | APPROVED 2026-04-10 — fallback gate tightened in `dashboard_server.py` so fresh authoritative stream marks are not superseded by fallback marks. `py_compile` PASS. Restart required. | `dashboard_server.py` |

## System-state line to replace
Replace the dashboard mark-source issue line with:

- **Dashboard mark-source issue: PATCHED, VERIFY PENDING** — `MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001` APPROVED. Fallback gate tightened so stream marks stay primary when fresh and `rest_fallback` is limited to truly missing/stale cases. `MARK_SOURCE_FALLBACK_RELIABILITY_VERIFY_001` ACTIVE after restart.

## Keep unchanged for now
- `BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001` is still needed and not yet opened.
- `RUNTIME_USER_STREAM_AUTH_UNBLOCK_001` remains blocked on user credentials.
