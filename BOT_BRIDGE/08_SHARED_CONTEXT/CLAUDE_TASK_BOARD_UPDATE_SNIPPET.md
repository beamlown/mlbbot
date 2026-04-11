# CLAUDE_TASK_BOARD_UPDATE_SNIPPET.md

Use this to update `08_SHARED_CONTEXT/CLAUDE_TASK_BOARD.md`.

## Header line
Replace the top header note with:

`## Last updated: 2026-04-10 — CONFIDENCE_GATE_LIVE_REBREAK_TRACE_002 approved. CONFIDENCE_GATE_RUNTIME_VERSION_TRACE_001 opened. 2 tasks tracked; 1 ACTIVE, 1 QUEUED.`

## ACTIVE section
Replace the ACTIVE section with:

| task_id | title | priority | subsystem | allowed_files | status |
|---------|-------|----------|-----------|---------------|--------|
| CONFIDENCE_GATE_RUNTIME_VERSION_TRACE_001 | Trace runtime code/version/process identity for low-confidence live opens | HIGH | read-only runtime/version trace | `bot_core.py`, `core/risk.py`, `core/model_bridge.py`, bot log, DB SELECT, pycache metadata, `.env` | ACTIVE — worker-ready. Brief in 05_INBOX. |

## QUEUED section
Replace QUEUED with:

| task_id | title | reason |
|---------|-------|--------|
| POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001 | Audit position card backed-team / held-side mismatch on live dashboard | Deferred until runtime/version trace identifies whether live gate behavior comes from stale code/process divergence. Higher-risk issue still takes precedence. |

## DONE row to add near the top of DONE
Add:
| task_id | title | outcome | allowed_files |
|---------|-------|---------|---------------|
| CONFIDENCE_GATE_LIVE_REBREAK_TRACE_002 | Trace exact live open path for current confidence-gate rebreak | APPROVED 2026-04-10 — within scoped current code, only one visible bridge open path was found and it already shows reject+continue before open_position(...). Most likely remaining explanation is runtime divergence / stale running code / version traceability failure. | `bot_core.py`, `core/model_bridge.py`, bot log, DB read-only |

## System-state line to replace
Replace the confidence-gate line with:

- **Confidence gate: LIVE REBREAK CONFIRMED, RUNTIME DIVERGENCE SUSPECTED** — current on-disk scoped bridge path appears correctly guarded, yet prior live runtime opened trades 241/243/244 below 0.60. `CONFIDENCE_GATE_RUNTIME_VERSION_TRACE_001` ACTIVE to prove what code/process/version was actually running.

Keep blocked credentials item unchanged.
