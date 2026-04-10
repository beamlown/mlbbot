# RISK_MANAGEMENT_MASTER_PLAN_001.md
## Sports Bot v2 — Risk Management Task Pack
### Issued: 2026-04-10

---

## System Truth to Preserve

These invariants must never be violated by any phase in this pack:

| Invariant | Formula / Rule |
|-----------|---------------|
| Live equity | `current_held_price * qty` |
| Unrealized PnL | `(current_held_price - entry_px) * qty` |
| Available cash | `lifetime_bankroll - capital_committed` |
| Current held price source | `_held_bid(trade.side, ob)` — held-side bid only. Never raw `bid_yes`/`bid_no`. |
| Lifetime bankroll | `INITIAL_BANKROLL + sum(pnl_usd for all closed trades since inception)` — never reset |
| TP threshold | `AUTO_TAKE_PROFIT_PCT = 0.40` (live post EXIT_PARAMS_TIGHTEN_001) |
| SL threshold | `AUTO_STOP_LOSS_PCT = 0.12` |
| Near-resolution price | `NEAR_RESOLUTION_PRICE = 0.97` |
| Trailing activate | `TRAILING_STOP_ACTIVATE_PCT = 0.10` |
| Trailing drawdown | `TRAILING_STOP_DRAWDOWN_PCT = 0.12` |
| Cooldown: near_resolution | 600s |
| Cooldown: stop_loss | 1800s |
| Cooldown: gap_stop | 3600s |
| Cooldown: take_profit / trailing_stop / market_resolved | NONE |

**Canonical held-side fields:**
`market_slug`, `held_token_id`, `held_contract_side`, `backed_team`, `faded_team`, `entry_price`, `current_held_price`, `qty`

---

## Phase Overview

| Phase | Task ID | Type | Gate Status | Allowed Files |
|-------|---------|------|-------------|---------------|
| 0 | RISK_PIPELINE_AUDIT_001 | Audit / read-only | **READY** | Read-only (no writes) |
| 1 | TP_SL_SCHEMA_NORMALIZATION_001 | Implementation | HOLD_PENDING_PHASE_0 | `core/risk.py`, `core/paper_exec.py`, `core/types.py` |
| 2 | POSITION_SIZING_RULES_001 | Implementation | HOLD_PENDING_PHASE_1 | `core/paper_exec.py`, `core/risk.py` |
| 3 | EXECUTION_RISK_MONITOR_001 | Implementation | HOLD_PENDING_PHASE_1 + RESOLUTION_WATCHER_INTEGRATE_001 | `bot_core.py`, `core/risk.py` |
| 4 | BANKROLL_SESSION_RULES_001 | Implementation | HOLD_PENDING_PHASES_2_AND_3 | `dashboard_server.py`, `core/paper_exec.py` |
| 5 | RISK_AND_TP_VERIFY_001 | Verification / read-only | HOLD_PENDING_PHASES_1_THROUGH_4 | Read-only (no writes) |
| 6 | RISK_AND_TP_AUDIT_001 | Audit / writeup | HOLD_PENDING_PHASE_5 | `08_SHARED_CONTEXT/RISK_MANAGEMENT_FINAL_AUDIT_001.md` only |

---

## Phase Descriptions

### Phase 0 — RISK_PIPELINE_AUDIT_001
**Type:** Spec/audit only — no code changes  
**Purpose:** Map the entire risk pipeline end-to-end. Produce `RISK_PIPELINE_AUDIT_REPORT_001.md` as the factual foundation for all later phases. Every gap, broken invariant, and immediate risk is listed with `file:line` citations.  
**Deliverables:** `RESULT_RISK_PIPELINE_AUDIT_001.json`, `08_SHARED_CONTEXT/RISK_PIPELINE_AUDIT_REPORT_001.md`  
**Gate:** READY — no dependencies, read-only, no file conflicts

---

### Phase 1 — TP_SL_SCHEMA_NORMALIZATION_001
**Type:** Implementation  
**Purpose:** Normalize how TP price, SL price, committed USD, and max loss USD are computed. All must derive from single canonical functions in `core/risk.py`. No threshold values change.  
**Deliverables:** `RESULT_TP_SL_SCHEMA_NORMALIZATION_001.json`  
**Gate:** HOLD — requires Phase 0 APPROVED

---

### Phase 2 — POSITION_SIZING_RULES_001
**Type:** Implementation  
**Purpose:** Define, document, and enforce position sizing: formula, confidence tiers, per-trade/per-session caps, liquidity gate. Produce `SIZING_RULES_SPEC_001.md`.  
**Deliverables:** `RESULT_POSITION_SIZING_RULES_001.json`, `08_SHARED_CONTEXT/SIZING_RULES_SPEC_001.md`  
**Gate:** HOLD — requires Phase 1 APPROVED. May run in parallel with Phase 3 if file sets don't overlap.

---

### Phase 3 — EXECUTION_RISK_MONITOR_001
**Type:** Implementation  
**Purpose:** Harden the runtime exit loop: empty-OB warnings, dummy-market warnings, exit-error logging upgrade, cooldown consistency. Fix the silent-skip bug where `_held_bid() = None` produces no log.  
**Deliverables:** `RESULT_EXECUTION_RISK_MONITOR_001.json`  
**Gate:** HOLD — requires Phase 1 APPROVED **AND** `RESOLUTION_WATCHER_INTEGRATE_001` APPROVED (both touch `bot_core.py`)

---

### Phase 4 — BANKROLL_SESSION_RULES_001
**Type:** Implementation  
**Purpose:** Enforce correct accounting: lifetime bankroll, session baseline, session PnL, available cash, capital committed, live equity. All canonical definitions verified in `dashboard_server.py` and `core/paper_exec.py`. Produce `BANKROLL_ACCOUNTING_SPEC_001.md`.  
**Deliverables:** `RESULT_BANKROLL_SESSION_RULES_001.json`, `08_SHARED_CONTEXT/BANKROLL_ACCOUNTING_SPEC_001.md`  
**Gate:** HOLD — requires Phases 2 AND 3 APPROVED

---

### Phase 5 — RISK_AND_TP_VERIFY_001
**Type:** Verification / read-only  
**Purpose:** End-to-end integration test of all prior phases. Verify TP/SL, sizing, held-side pricing, close logic, and bankroll all agree. DB vs dashboard reconciliation. Produce `RISK_VERIFY_REPORT_001.md`.  
**Deliverables:** `RESULT_RISK_AND_TP_VERIFY_001.json`, `08_SHARED_CONTEXT/RISK_VERIFY_REPORT_001.md`  
**Gate:** HOLD — requires Phases 1, 2, 3, 4 all APPROVED

---

### Phase 6 — RISK_AND_TP_AUDIT_001
**Type:** Audit / writeup  
**Purpose:** Final human-readable reference document for the entire risk system: file map, TP/SL architecture, sizing formula, held-side pricing chain, bankroll accounting, verification results, gaps table, recommended next actions.  
**Deliverables:** `RESULT_RISK_AND_TP_AUDIT_001.json`, `08_SHARED_CONTEXT/RISK_MANAGEMENT_FINAL_AUDIT_001.md`  
**Gate:** HOLD — requires Phase 5 APPROVED

---

## Dependency Graph

```
Phase 0 (Audit) ──────────────────────────────────────────┐
         └──► Phase 1 (Schema Normalization)               │
                   ├──► Phase 2 (Sizing Rules)             │
                   │         └──────────────┐              │
                   └──► Phase 3 (Exec Monitor)*            │
                                   └─────────┴──► Phase 4 (Bankroll)
                                                     └──► Phase 5 (Verify)
                                                               └──► Phase 6 (Audit)

* Phase 3 also requires RESOLUTION_WATCHER_INTEGRATE_001 (separate task pack)
```

---

## Pre-existing Approved Work (Do Not Re-do)

| Task | Outcome | Preserved By |
|------|---------|-------------|
| EXECUTION_HELD_SIDE_SEMANTICS_001 | Held-contract semantics fixed in `core/risk.py` and `core/paper_exec.py` | All phases must preserve `_held_bid()` as canonical |
| EXIT_PARAMS_TIGHTEN_001 | TP=0.40, SL=0.12, NRP=0.97, trailing 0.10/0.12 live in `.env` | No phase may change these without explicit manager approval |
| SL_COOLDOWN_001 | stop_loss=1800s, gap_stop=3600s cooldowns live in `bot_core.py` | Phase 3 must verify and preserve these |
| BOT_DATE_GATE_DEFENSE_001 | Date gate in `bot_core.py` local origination path | Phase 3 must not disturb this |
| STALE_MARK_REST_FALLBACK_001 | REST fallback for stale marks in `dashboard_server.py` | Phase 4 must preserve this |

---

## Out of Scope for This Pack

- MLB model strategy or decision logic (`mlb_model/`)
- Dashboard UI aesthetics
- Polymarket CLOB execution (live order routing — paper trading only)
- Resolution watcher (covered by separate task pack: RESOLUTION_WATCHER_BUILD_001 / INTEGRATE_001)
- Any fake bankroll resets or history erasure

---

## Dashboard Target

`localhost:8900` for all manual verification unless code proves otherwise.
