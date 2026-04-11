# CLAUDE_TASK_BOARD_UPDATE_SNIPPET.md

Use this to update `08_SHARED_CONTEXT/CLAUDE_TASK_BOARD.md`.

## Header line
Replace the top header note with:

`## Last updated: 2026-04-10 — CONFIDENCE_GATE_LIVE_REBREAK_001 reviewed APPROVED. CONFIDENCE_GATE_LIVE_REBREAK_FIX_001 opened. 2 tasks tracked; 1 ACTIVE, 1 QUEUED.`

## ACTIVE section
Replace the ACTIVE section with:

| task_id | title | priority | subsystem | allowed_files | status |
|---------|-------|----------|-----------|---------------|--------|
| CONFIDENCE_GATE_LIVE_REBREAK_FIX_001 | Fix live confidence gate rebreak so sub-0.60 signals cannot open after gate rejection | HIGH | risk / entry-gating / bridge open flow | `bot_core.py`; `core/model_bridge.py` only if strictly required | ACTIVE — worker-ready. Brief in 05_INBOX. |

## QUEUED section
Replace QUEUED with:

| task_id | title | reason |
|---------|-------|--------|
| POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001 | Audit position card backed-team / held-side mismatch on live dashboard | Deferred until current confidence-gate live rebreak fix is addressed. Higher-risk trading issue takes precedence. |

## DONE row to add near the top of DONE
| task_id | title | outcome | allowed_files |
|---------|-------|---------|---------------|
| CONFIDENCE_GATE_LIVE_REBREAK_001 | Re-verify live confidence gate after restart and identify current bypass path | APPROVED 2026-04-10 — current live rebreak confirmed. New live trades opened below 0.60 despite reject evidence at 0.600 in the same runtime. Root cause is a live gate/open ordering inconsistency or bypass, not simple config drift. | `core/risk.py`, `core/model_bridge.py`, `.env`, bot log, DB read-only |

## System-state line to replace
Replace the confidence-gate line with:

- **Confidence gate: LIVE REBREAK CONFIRMED** — current runtime opened new trades 241/243/244 at 0.3863 / 0.3279 / 0.3769. `CONFIDENCE_GATE_LIVE_REBREAK_001` APPROVED. `CONFIDENCE_GATE_LIVE_REBREAK_FIX_001` ACTIVE to eliminate the current live gate/open inconsistency.

Keep the blocked credentials item unchanged.
