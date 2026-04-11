# CLAUDE_TASK_BOARD_UPDATE_SNIPPET.md

Use this to update `08_SHARED_CONTEXT/CLAUDE_TASK_BOARD.md`.

## Header line
Replace the top header note with:

`## Last updated: 2026-04-11 — MIN_ENTRY_PRICE_GATE_001, TP_NEAR_RESOLUTION_CAP_FIX_001, and BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001 approved. MARKET_COOLDOWN_PERSIST_001 promoted to ACTIVE.`

## ACTIVE section
Replace the ACTIVE section with:

| task_id | title | priority | subsystem | allowed_files | status |
|---------|-------|----------|-----------|---------------|--------|
| MARKET_COOLDOWN_PERSIST_001 | Persist market cooldown across restarts | HIGH | risk / market cooldown persistence | `bot_core.py`; tiny directly related state path only if strictly required | ACTIVE — worker-ready. Brief in 05_INBOX. |
| MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001 | Trace mark-source fallback frequency and guard-message payload origin | MEDIUM | read-only trace — dashboard_server / stream / runtime state | runtime/state.json, dashboard_server.py, logs/dashboard.log, logs/dashboard_err.log | ACTIVE — read-only, non-conflicting. |

## QUEUED section
Replace QUEUED with:

| task_id | title | priority | blocked_by | notes |
|---------|-------|----------|------------|-------|
| SESSION_PNL_TRUE_START_FIX_001 | Track true session PnL from actual session start, not last restart | MEDIUM | All critical risk fixes DONE | Dashboard visibility only |
| POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001 | Audit position card backed-team / held-side mismatch on live dashboard | MEDIUM | Critical risk fixes remain higher priority | Keep queued until risk stack is stabilized |

## DONE rows to add near the top of DONE
Add these entries near the top of DONE:

| task_id | title | outcome | allowed_files |
|---------|-------|---------|---------------|
| BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001 | Prevent duplicate/repeated slug intents from bypassing gate protections in the same bridge loop | APPROVED 2026-04-10 — minimal per-loop consumed-slug guard added in `bot_core.py` so a slug rejected, skipped, or opened once cannot re-enter later in the same iteration. `py_compile` PASS. Restart required. | `bot_core.py` |
| TP_NEAR_RESOLUTION_CAP_FIX_001 | Fix unreachable TP math for near-1.0 entries | APPROVED 2026-04-10 — `get_tp_price(trade)` now caps TP at the near-resolution ceiling so near-1.0 entries cannot compute unreachable TP values above the meaningful contract limit. `py_compile` PASS. Restart required. | `core/risk.py` |
| MIN_ENTRY_PRICE_GATE_001 | Add minimum entry price gate to prevent instant stop-loss churn on ultra-low-price entries | APPROVED 2026-04-10 — minimal gate added to `check_entry_gates()` in `core/risk.py` with default threshold 0.15 and correct side-specific ask handling. `py_compile` PASS. Restart required. | `core/risk.py` |

## Conflict map guidance
Update the conflict map so:
- `bot_core.py` is locked by `MARKET_COOLDOWN_PERSIST_001`
- `core/risk.py` is no longer ACTIVE-locked by `MIN_ENTRY_PRICE_GATE_001`
- `MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001` remains read-only/non-exclusive
