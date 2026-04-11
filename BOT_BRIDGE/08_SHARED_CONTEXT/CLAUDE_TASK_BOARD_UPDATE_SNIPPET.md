# CLAUDE_TASK_BOARD_UPDATE_SNIPPET.md

Use this to update `08_SHARED_CONTEXT/CLAUDE_TASK_BOARD.md`.

## Header line
Replace the top header note with:

`## Last updated: 2026-04-10 — BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001 approved. MARKET_COOLDOWN_PERSIST_001 promoted to ACTIVE. 2 ACTIVE tasks.`

## ACTIVE section
Replace the ACTIVE section with:

| task_id | title | priority | subsystem | allowed_files | status |
|---------|-------|----------|-----------|---------------|--------|
| MARKET_COOLDOWN_PERSIST_001 | Persist market cooldown across restarts | HIGH | risk / market cooldown persistence | `bot_core.py`; tiny directly related state path only if strictly required | ACTIVE — worker-ready. Brief in 05_INBOX. |
| MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001 | Trace mark-source fallback frequency and guard-message payload origin | MEDIUM | read-only trace — dashboard_server / stream / runtime state | runtime/state.json, dashboard_server.py, logs/dashboard.log, logs/dashboard_err.log | ACTIVE — read-only, non-conflicting. |

## QUEUED section
Leave queued ordering as:
1. SESSION_PNL_TRUE_START_FIX_001
2. POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001

## DONE row to add near the top of DONE
Add:

| task_id | title | outcome | allowed_files |
|---------|-------|---------|---------------|
| BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001 | Prevent duplicate/repeated slug intents from bypassing gate protections in the same bridge loop | APPROVED 2026-04-10 — minimal per-loop consumed-slug guard added in `bot_core.py` so a slug rejected, skipped, or opened once cannot re-enter later in the same iteration. `py_compile` PASS. Restart required. | `bot_core.py` |

## System-state line to replace
Replace the duplicate-slug/open-item line with:

- **Duplicate-slug gate bug: PATCHED, VERIFY PENDING** — `BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001` APPROVED. Per-loop consumed-slug protection is now in `bot_core.py`. Restart required before live protection is trusted.

Keep pycache/cold-restart operator action prominent.
