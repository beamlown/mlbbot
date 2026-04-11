# CLAUDE_TASK_BOARD_UPDATE_SNIPPET.md

Use this to update `08_SHARED_CONTEXT/CLAUDE_TASK_BOARD.md`.

## Header line
Replace the top header note with:

`## Last updated: 2026-04-10 — POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001 approved. POSITION_SIDE_SEMANTICS_MERGE_FIX_001 promoted to ACTIVE. 2 ACTIVE tasks.`

## ACTIVE section
Replace the ACTIVE section with:

| task_id | title | priority | subsystem | allowed_files | status |
|---------|-------|----------|-----------|---------------|--------|
| POSITION_SIDE_SEMANTICS_MERGE_FIX_001 | Fix stale client-side merge overwriting backed-team and side semantics | HIGH | dashboard truth / side semantics | `dashboard.html` | ACTIVE — worker-ready. Brief in 05_INBOX. |
| MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001 | Trace mark-source fallback frequency and guard-message payload origin | MEDIUM | read-only trace — dashboard_server / stream / runtime state | runtime/state.json, dashboard_server.py, logs/dashboard.log, logs/dashboard_err.log | ACTIVE — read-only, non-conflicting. |

## QUEUED section
Replace QUEUED with:

_None._

## DONE row to add near the top of DONE
Add:

| task_id | title | outcome | allowed_files |
|---------|-------|---------|---------------|
| POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001 | Audit position card backed-team / held-side mismatch on live dashboard | APPROVED 2026-04-10 — execution truth and server payload mapping clean. Root cause traced to dashboard.html client-side full-object merge in renderUnifiedPositions(); stale cached markMap fields overwrite current trade side semantics. Secondary Games-tab slug-key mismatch also identified. | `runtime/state.json`, `dashboard_server.py`, `dashboard.html`, DB SELECT if needed |

## System-state line to replace
Replace the dashboard side-truth line with:

- **Dashboard side-truth issue: ROOT CAUSE FOUND, FIX ACTIVE** — `POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001` traced the mismatch to a stale client-side merge in `dashboard.html`. `POSITION_SIDE_SEMANTICS_MERGE_FIX_001` is now ACTIVE to protect semantic identity fields from stale cache overwrite.

## Keep unchanged for now
- pycache/cold-restart operator action remains prominent
- `MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001` remains read-only and non-conflicting
- user/fill stream credentials remain blocked on Johnny
