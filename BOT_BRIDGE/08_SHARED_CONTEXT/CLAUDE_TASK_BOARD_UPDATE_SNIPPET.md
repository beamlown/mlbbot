# CLAUDE_TASK_BOARD_UPDATE_SNIPPET.md

Use this to update `08_SHARED_CONTEXT/CLAUDE_TASK_BOARD.md`.

## Header line
Replace the top header note with:

`## Last updated: 2026-04-10 — TP_NEAR_RESOLUTION_CAP_FIX_001 approved. BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001 promoted to ACTIVE. 2 ACTIVE tasks.`

## ACTIVE section
Replace the ACTIVE section with:

| task_id | title | priority | subsystem | allowed_files | status |
|---------|-------|----------|-----------|---------------|--------|
| BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001 | Prevent duplicate/repeated slug intents from bypassing gate protections in the same bridge loop | HIGH | bridge entry gating / duplicate intent handling | `bot_core.py`; `core/model_bridge.py` only if strictly required | ACTIVE — worker-ready. Brief in 05_INBOX. |
| MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001 | Trace mark-source fallback frequency and guard-message payload origin | MEDIUM | read-only trace — dashboard_server / stream / runtime state | runtime/state.json, dashboard_server.py, logs/dashboard.log, logs/dashboard_err.log | ACTIVE — read-only, non-conflicting. |

## QUEUED section
Leave queued ordering as:
1. MARKET_COOLDOWN_PERSIST_001
2. SESSION_PNL_TRUE_START_FIX_001
3. POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001 (still deprioritized behind critical risk items if your board currently includes it)

## DONE row to add near the top of DONE
Add:

| task_id | title | outcome | allowed_files |
|---------|-------|---------|---------------|
| TP_NEAR_RESOLUTION_CAP_FIX_001 | Fix unreachable TP math for near-1.0 entries | APPROVED 2026-04-10 — `get_tp_price(trade)` now caps TP at the near-resolution ceiling so near-1.0 entries cannot compute unreachable TP values above the meaningful contract limit. `py_compile` PASS. Restart required. | `core/risk.py` |

## System-state line to replace
Replace the near-resolution TP bug/open-item line with:

- **Near-resolution TP bug: PATCHED, VERIFY PENDING** — `TP_NEAR_RESOLUTION_CAP_FIX_001` APPROVED. `get_tp_price(trade)` now caps unreachable TP values for near-1.0 entries. Restart required before live protection is trusted.

Keep pycache/cold-restart operator action prominent.
