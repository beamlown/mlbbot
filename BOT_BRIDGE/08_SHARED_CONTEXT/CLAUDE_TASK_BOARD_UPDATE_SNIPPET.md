# CLAUDE_TASK_BOARD_UPDATE_SNIPPET.md

Use this to update `08_SHARED_CONTEXT/CLAUDE_TASK_BOARD.md`.

## Header line
Replace the top header note with:

`## Last updated: 2026-04-10 — MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001 approved. Two new live audits opened: CONFIDENCE_GATE_LIVE_REBREAK_001 and POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001. 2 ACTIVE tasks.`

## ACTIVE table
Replace the ACTIVE section with:

| task_id | title | priority | subsystem | allowed_files | status |
|---------|-------|----------|-----------|---------------|--------|
| CONFIDENCE_GATE_LIVE_REBREAK_001 | Re-verify live confidence gate after restart and identify current bypass path | HIGH | read-only runtime audit | `runtime/state.json`, `logs/bot_baseball_20260410.log`, `bot_core.py`, `core/risk.py`, `.env`, `trades_sports.db (SELECT only)` | ACTIVE — worker-ready. Brief in 05_INBOX. |
| POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001 | Audit position card backed-team / held-side mismatch on live dashboard | HIGH | read-only display-truth audit | `runtime/state.json`, `dashboard_server.py`, `dashboard.html`, `trades_sports.db (SELECT only if needed)`, `logs/dashboard.log` | ACTIVE — worker-ready. Brief in 05_INBOX. |

## DONE rows to add near the top of DONE
| task_id | title | outcome | allowed_files |
|---------|-------|---------|---------------|
| MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001 | Reduce inaccurate rest_fallback usage and preserve live stream mark authority | APPROVED 2026-04-10 — fallback gate tightened in `dashboard_server.py` so fresh authoritative stream marks are not superseded by fallback marks. `py_compile` PASS. Restart completed. | `dashboard_server.py` |
| MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001 | Trace mark-source fallback frequency and guard-message payload origin | PARTIAL PASS 2026-04-10 — mark REST chain traced end-to-end. `rest_fallback` confirmed as expected UI behavior, not a front-end bug. Guard/max-down wording not found in current runtime/dashboard payload. Upstream fallback quality issue identified. | runtime/state.json, dashboard_server.py, dashboard.html, dashboard.log, bot log (read-only) |

## System-state lines to replace
Replace the confidence-gate line with:

- **Confidence gate: LIVE REBREAK SUSPECTED** — despite prior wiring fix and restart attempts, current runtime now shows new open trades 241/243/244 with confidence 0.3863 / 0.3279 / 0.3769. `CONFIDENCE_GATE_LIVE_REBREAK_001` ACTIVE to identify the current bypass path.

Replace the dashboard display issues line with:

- **Dashboard side-truth issue: LIVE AUDIT OPEN** — operator reports the dashboard sometimes shows the bot backing the wrong team. `POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001` ACTIVE to trace execution truth -> payload -> card labeling and locate the mismatch.

Keep blocked credentials item unchanged.
