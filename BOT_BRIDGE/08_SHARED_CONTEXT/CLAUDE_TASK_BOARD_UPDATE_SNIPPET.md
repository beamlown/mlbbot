# CLAUDE_TASK_BOARD_UPDATE_SNIPPET.md

Use this to update `08_SHARED_CONTEXT/CLAUDE_TASK_BOARD.md`.

## Header line
Replace the top header note with:

`## Last updated: 2026-04-10 — CONFIDENCE_GATE_RUNTIME_VERSION_TRACE_001 approved. POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001 promoted to ACTIVE. 1 ACTIVE task.`

## ACTIVE section
Replace the ACTIVE section with:

| task_id | title | priority | subsystem | allowed_files | status |
|---------|-------|----------|-----------|---------------|--------|
| POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001 | Audit position card backed-team / held-side mismatch on live dashboard | HIGH | read-only display-truth audit | `runtime/state.json`, `dashboard_server.py`, `dashboard.html`, `trades_sports.db (SELECT only if needed)`, `logs/dashboard.log` | ACTIVE — worker-ready. Brief already in 05_INBOX. |

## QUEUED section
Replace QUEUED with:

_None._

## DONE row to add near the top of DONE
Add:

| task_id | title | outcome | allowed_files |
|---------|-------|---------|---------------|
| CONFIDENCE_GATE_RUNTIME_VERSION_TRACE_001 | Trace runtime code/version/process identity for low-confidence live opens | APPROVED 2026-04-10 — strongest supported conclusion is runtime divergence / stale prior process state. Bad opens around 19:00 local predated the currently running launcher/process (~19:50 local). Current on-disk `bot_core.py` already shows guarded reject+continue flow. | `bot_core.py`, bot log, DB read-only |

## System-state line to replace
Replace the confidence-gate line with:

- **Confidence gate: EARLIER LIVE REBREAK MOST LIKELY FROM STALE PRIOR PROCESS STATE** — runtime version trace found the bad low-confidence opens predated the currently running launcher/process, while current on-disk `bot_core.py` already shows guarded reject+continue flow. No new blind logic patch opened. Future hardening follow-on recommended: runtime code/version fingerprint logging.

Replace the dashboard side-truth line with:

- **Dashboard side-truth issue: ACTIVE** — operator reports the dashboard sometimes shows the bot backing the wrong team. `POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001` is now the active worker task.

## Keep unchanged for now
- `RUNTIME_USER_STREAM_AUTH_UNBLOCK_001` remains blocked on user credentials.
- Optional future hardening: runtime code/version fingerprint logging (not opened in this pass).
