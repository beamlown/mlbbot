# CLAUDE_TASK_BOARD_UPDATE_SNIPPET.md

Use this to update `08_SHARED_CONTEXT/CLAUDE_TASK_BOARD.md`.

## Header line
Replace the top header note with:

`## Last updated: 2026-04-10 — MARKET_COOLDOWN_PERSIST_001 approved. SESSION_PNL_TRUE_START_FIX_001 promoted to ACTIVE. 2 ACTIVE tasks.`

## ACTIVE section
Replace the ACTIVE section with:

| task_id | title | priority | subsystem | allowed_files | status |
|---------|-------|----------|-----------|---------------|--------|
| SESSION_PNL_TRUE_START_FIX_001 | Track true session PnL from actual session start, not last restart | MEDIUM | dashboard visibility / session accounting | `bot_core.py`, `dashboard_server.py` | ACTIVE — worker-ready. Brief in 05_INBOX. |
| MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001 | Trace mark-source fallback frequency and guard-message payload origin | MEDIUM | read-only trace — dashboard_server / stream / runtime state | runtime/state.json, dashboard_server.py, logs/dashboard.log, logs/dashboard_err.log | ACTIVE — read-only, non-conflicting. |

## QUEUED section
Replace QUEUED with:

| task_id | title | priority | blocked_by | notes |
|---------|-------|----------|------------|-------|
| POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001 | Audit position card backed-team / held-side mismatch on live dashboard | MEDIUM | Risk fixes remain higher priority | Keep queued until risk/visibility fixes are stabilized |

## DONE row to add near the top of DONE
Add:

| task_id | title | outcome | allowed_files |
|---------|-------|---------|---------------|
| MARKET_COOLDOWN_PERSIST_001 | Persist market cooldown across restarts | APPROVED 2026-04-10 — `bot_core.py` now writes non-expired cooldowns to runtime state and reloads them on startup so restart no longer wipes active cooldowns. `py_compile` PASS. Restart required. | `bot_core.py` |

## System-state line to replace
Replace the market cooldown/open-item line with:

- **Market cooldown persistence: PATCHED, VERIFY PENDING** — `MARKET_COOLDOWN_PERSIST_001` APPROVED. Cooldown expiries are now persisted to runtime state and restored on startup. Restart required before live protection is trusted, and stale bot_core pycache must still be cleared.
