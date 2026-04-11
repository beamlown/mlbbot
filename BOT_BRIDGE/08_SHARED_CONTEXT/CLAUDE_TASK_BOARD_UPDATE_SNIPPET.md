# CLAUDE_TASK_BOARD_UPDATE_SNIPPET.md

Use this to update `08_SHARED_CONTEXT/CLAUDE_TASK_BOARD.md`.

## Header line
Replace the top header note with:

`## Last updated: 2026-04-10 — POSITION_SIDE_SEMANTICS_MERGE_FIX_001 approved. Dashboard side-semantics fix complete. 1 ACTIVE task.`

## ACTIVE section
Replace the ACTIVE section with:

| task_id | title | priority | subsystem | allowed_files | status |
|---------|-------|----------|-----------|---------------|--------|
| MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001 | Trace mark-source fallback frequency and guard-message payload origin | MEDIUM | read-only trace — dashboard_server / stream / runtime state | runtime/state.json, dashboard_server.py, logs/dashboard.log, logs/dashboard_err.log | ACTIVE — read-only, non-conflicting. |

## QUEUED section
Replace QUEUED with:

_None._

## DONE row to add near the top of DONE
Add:

| task_id | title | outcome | allowed_files |
|---------|-------|---------|---------------|
| POSITION_SIDE_SEMANTICS_MERGE_FIX_001 | Fix stale client-side merge overwriting backed-team and side semantics | APPROVED 2026-04-10 — `dashboard.html` now uses a field-specific safe merge in `renderUnifiedPositions()` so stale cached mark data cannot overwrite current trade identity fields; Games-tab slug-key mismatch also fixed. No restart required; browser hard refresh required. | `dashboard.html` |

## System-state line to replace
Replace the dashboard side-truth line with:

- **Dashboard side-truth issue: PATCHED** — `POSITION_SIDE_SEMANTICS_MERGE_FIX_001` APPROVED. `dashboard.html` now protects current trade semantic identity fields from stale cache overwrite, and the Games-tab slug lookup has been normalized. Browser hard refresh required.

## Keep unchanged for now
- pycache/cold-restart operator action remains prominent for bot_core-backed fixes
- `MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001` remains read-only and non-conflicting until reviewed/closed
- user/fill stream credentials remain blocked on Johnny
