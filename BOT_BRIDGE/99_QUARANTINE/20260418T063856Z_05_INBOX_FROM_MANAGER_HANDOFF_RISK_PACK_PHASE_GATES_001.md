# HANDOFF_RISK_PACK_PHASE_GATES_001.md
## Risk Management Task Pack — Phase Gate Rules
### Issued: 2026-04-10

---

## Purpose

This handoff document defines the sequencing rules, gate conditions, and file lock rules for the risk management task pack. Workers must read this before starting any phase task.

---

## Phase Sequence and Gates

```
[RESOLUTION_WATCHER_BUILD_001]     ← currently ACTIVE (integration/ files only)
         ↓ APPROVED
[RESOLUTION_WATCHER_INTEGRATE_001] ← QUEUED (bot_core.py)
         ↓ APPROVED
         ↓
[RISK_PIPELINE_AUDIT_001]          ← Phase 0 — READY NOW (read-only, no file conflict)
         ↓ APPROVED
[TP_SL_SCHEMA_NORMALIZATION_001]   ← Phase 1 — core/risk.py, core/paper_exec.py, core/types.py
         ↓ APPROVED
         ├──────────────────────────────────────────┐
[POSITION_SIZING_RULES_001]        [EXECUTION_RISK_MONITOR_001]
Phase 2 — core/paper_exec.py       Phase 3 — bot_core.py, core/risk.py
core/risk.py (sizing only)         *** ALSO requires RESOLUTION_WATCHER_INTEGRATE_001 ***
         ↓ APPROVED                         ↓ APPROVED
         └──────────────┬───────────────────┘
                        ↓
            [BANKROLL_SESSION_RULES_001]    ← Phase 4 — dashboard_server.py, core/paper_exec.py
                        ↓ APPROVED
            [RISK_AND_TP_VERIFY_001]        ← Phase 5 — read-only
                        ↓ APPROVED
            [RISK_AND_TP_AUDIT_001]         ← Phase 6 — writeup only
```

**Key constraint:** Phase 2 (POSITION_SIZING_RULES_001) and Phase 3 (EXECUTION_RISK_MONITOR_001) may run in parallel IF their file sets do not overlap AND both dependencies are met. Phase 3 requires RESOLUTION_WATCHER_INTEGRATE_001 to be APPROVED before touching bot_core.py.

---

## File Lock Table

| File | Locked By Phase | Notes |
|------|----------------|-------|
| `integration/__init__.py` | RESOLUTION_WATCHER_BUILD_001 | Released after APPROVED |
| `integration/resolution_watcher.py` | RESOLUTION_WATCHER_BUILD_001 | Released after APPROVED |
| `bot_core.py` | RESOLUTION_WATCHER_INTEGRATE_001 → Phase 3 | Phase 3 must wait for INTEGRATE_001 |
| `core/risk.py` | Phase 1 → Phase 3 (sequentially) | Phase 1 must be APPROVED before Phase 3 starts |
| `core/paper_exec.py` | Phase 1 → Phase 2 → Phase 4 (sequentially) | No two phases may touch simultaneously |
| `core/types.py` | Phase 1 only | Only if audit proves schema fields missing |
| `dashboard_server.py` | Phase 4 only | |

---

## Strict Rules for All Workers

1. **Never start a phase task until all listed dependencies are APPROVED.** "I think it's close" is not APPROVED.
2. **Never touch a file not in your task's `allowed_files`.** Even a one-line comment in an out-of-scope file is a scope violation.
3. **Never change TP/SL threshold values** unless a task explicitly grants permission.
4. **Never fake a bankroll reset.** Session baselines are snapshots, not DB writes.
5. **Never reintroduce raw YES/NO bid prices** into equity, PnL, or exit calculations. Use `_held_bid()` or equivalent.
6. **Every claim must cite file:line_number.** Paraphrasing code is not acceptable in deliverables.
7. **py_compile must pass** for every file touched before submitting a result.

---

## System Truths That Must Not Be Changed

- `live_equity = current_held_price * qty`
- `unrealized_pnl = (current_held_price - entry_px) * qty`
- `available_cash = lifetime_bankroll - capital_committed`
- `current_held_price` comes from `_held_bid(trade.side, ob)` — held-side only
- `lifetime_bankroll = INITIAL_BANKROLL + sum(pnl_usd for all closed trades since inception)` — never reset
- TP/SL thresholds post EXIT_PARAMS_TIGHTEN_001: TP=0.40, SL=0.12, NRP=0.97, trailing_activate=0.10, trailing_drawdown=0.12

---

## Phase 0 Is READY Now

RISK_PIPELINE_AUDIT_001 is read-only and has no file conflicts with the currently active RESOLUTION_WATCHER_BUILD_001. It may start immediately.

All other phases are HOLD until their dependencies are APPROVED.

---

## Dashboard Target

Use `localhost:8900` for all manual dashboard verification steps unless code explicitly shows a different port.
