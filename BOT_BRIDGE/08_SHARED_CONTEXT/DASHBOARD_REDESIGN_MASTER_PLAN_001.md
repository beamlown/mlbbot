# DASHBOARD_REDESIGN_MASTER_PLAN_001

## Gate Status: CLEARED — READY

`EXECUTION_HELD_SIDE_SEMANTICS_001` APPROVED (commit 2dbb3fc). `REVIEW_EXECUTION_HELD_SIDE_SEMANTICS_001.md` written to `07_REVIEWS`.

**DASHBOARD_REDESIGN_ARCH_001 is now ACTIVE.** Worker may begin Phase 0.

---

## Phase Order

| Phase | Task ID | Type | Allowed Files | Status |
|-------|---------|------|---------------|--------|
| 0 | DASHBOARD_REDESIGN_ARCH_001 | spec only | _(none — read only)_ | **DONE** |
| 1 | DASHBOARD_REDESIGN_SHELL_001 | implementation | `dashboard.html` | **DONE** |
| 2 | DASHBOARD_LIVE_COMMAND_CENTER_001 | implementation | `dashboard.html`, `dashboard_server.py`* | **DONE** |
| 3 | DASHBOARD_POSITIONS_HISTORY_SYSTEM_001 | implementation | `dashboard.html`, `dashboard_server.py`* | **DONE** |
| 4 | DASHBOARD_PERFORMANCE_POLISH_001 | implementation | `dashboard.html` | **DONE** |
| 5 | DASHBOARD_REDESIGN_VERIFY_001 | verification | _(none — read only)_ | **DONE** |
| 6 | DASHBOARD_REDESIGN_AUDIT_001 | audit | _(none — read only)_ | **DONE** |
| 7 | DASHBOARD_REDESIGN_LIVE_SMOKE_001 | verification | _(none — read only)_ | **DONE** |

\* `dashboard_server.py` only if a required field is genuinely absent from existing API responses. Must be documented and justified in the result.

---

## Phase Summaries

### Phase 0 — DASHBOARD_REDESIGN_ARCH_001 (spec only)
Read current dashboard.html and dashboard_server.py. Write `DASHBOARD_REDESIGN_SPEC_001.md` to `08_SHARED_CONTEXT`. Define tabs, payload mapping, focal areas, demotion list, truth-model preservation checklist. Zero code changes.

### Phase 1 — DASHBOARD_REDESIGN_SHELL_001 (shell)
Implement dark premium layout, 5-tab navigation, persistent command bar. Tabs are empty containers. Preserve all existing JS functions. No data binding yet. `dashboard.html` only.

### Phase 2 — DASHBOARD_LIVE_COMMAND_CENTER_001 (LIVE tab)
Populate LIVE tab: game monitor, position cards with held-contract truth, account strip. Position cards use `bid_no` for BUY_NO, `bid_yes` for BUY_YES. Backed_team semantics. In-place SSE updates. `dashboard.html` primary; `dashboard_server.py` only if needed.

### Phase 3 — DASHBOARD_POSITIONS_HISTORY_SYSTEM_001 (secondary tabs)
Populate POSITIONS, GAMES, HISTORY, SYSTEM tabs. Advisory allowed in GAMES tab only (muted, labeled). No shadow in POSITIONS or HISTORY. SYSTEM shows stream health. `dashboard.html` primary.

### Phase 4 — DASHBOARD_PERFORMANCE_POLISH_001 (polish)
Eliminate flicker, convert full re-renders to in-place updates, remove CSS transitions from numeric values, add loading states. No truth-model changes. `dashboard.html` only.

### Phase 5 — DASHBOARD_REDESIGN_VERIFY_001 (verification)
Read-only. Verify BUY_NO pricing uses `bid_no`. Verify unrealized sign correct. Verify shadow excluded from LIVE tab. Verify incidents (SEA/TEX, BOS/MIL) cannot recur in display layer. Write result JSON to `06_OUTBOX_FROM_WORKER`.

### Phase 6 — DASHBOARD_REDESIGN_AUDIT_001 (audit)
Read-only. Compare implementation against `DASHBOARD_REDESIGN_SPEC_001.md` item by item. Write audit report to `08_SHARED_CONTEXT`. Issue incident closure statements. Produce overall verdict.

---

## Truth Model Constraints (enforced across all phases)

| Constraint | Rule |
|---|---|
| `current_held_price` for BUY_YES | `bid_yes` from SSE stream |
| `current_held_price` for BUY_NO | `bid_no` from SSE stream — **never `bid_yes`** |
| `unrealized_pct` | `(current_held_price - entry_px) / entry_px` — same formula both sides |
| Price authority chain | polymarket stream → state_hub → SSE → frontend |
| Shadow/advisory | GAMES tab only, clearly labeled, never in LIVE or POSITIONS |
| No new price writers | No JS code may compute or override `current_held_price` outside SSE handler |
| Backed team semantics | `backed_team` / `faded_team` on display — not raw YES/NO slug |
| Fallback label | If stream stale >30s, show STALE badge on affected prices |

---

## Execution Gate Sequence

```
EXECUTION_HELD_SIDE_SEMANTICS_001 APPROVED
    ↓
DASHBOARD_REDESIGN_ARCH_001 → APPROVED → DASHBOARD_REDESIGN_SPEC_001.md written
    ↓
DASHBOARD_REDESIGN_SHELL_001 → APPROVED → shell live at localhost:8900
    ↓
DASHBOARD_LIVE_COMMAND_CENTER_001 → APPROVED → LIVE tab functional
    ↓
DASHBOARD_POSITIONS_HISTORY_SYSTEM_001 → APPROVED → all 5 tabs functional
    ↓
DASHBOARD_PERFORMANCE_POLISH_001 → APPROVED → no flicker, smooth
    ↓
DASHBOARD_REDESIGN_VERIFY_001 → APPROVED (PASS) → truth model verified
    ↓
DASHBOARD_REDESIGN_AUDIT_001 → APPROVED → DASHBOARD_REDESIGN_AUDIT_REPORT_001.md written
    ↓
REDESIGN COMPLETE
```

---

## Files This Pack Will Touch

| File | Phases |
|------|--------|
| `dashboard.html` | 1, 2, 3, 4 |
| `dashboard_server.py` | 2 or 3 only if a field is genuinely absent (may not be touched at all) |
| `08_SHARED_CONTEXT/DASHBOARD_REDESIGN_SPEC_001.md` | 0 (created) |
| `08_SHARED_CONTEXT/DASHBOARD_REDESIGN_AUDIT_REPORT_001.md` | 6 (created) |

**Do not touch:** `bot_core.py`, `core/risk.py`, `core/paper_exec.py`, `core/db.py`, `core/model_bridge.py`, `core/types.py`, `mlb_model/`

---

## Current State (2026-04-08)

- `EXECUTION_HELD_SIDE_SEMANTICS_001`: **APPROVED — commit 2dbb3fc** ← gate cleared
- `DASHBOARD_REDESIGN_ARCH_001`: **DONE — spec at 08_SHARED_CONTEXT/DASHBOARD_REDESIGN_SPEC_001.md**
- `DASHBOARD_REDESIGN_SHELL_001`: **DONE — commit 552686f**
- `DASHBOARD_LIVE_COMMAND_CENTER_001`: **DONE — commit 2e7bfcc**
- `DASHBOARD_POSITIONS_HISTORY_SYSTEM_001`: **DONE — commits fa12342 + f9d7f25**
- `DASHBOARD_PERFORMANCE_POLISH_001`: **DONE — commit a19f421**
- `DASHBOARD_REDESIGN_VERIFY_001`: **DONE — PASS**
- `DASHBOARD_REDESIGN_AUDIT_001`: **DONE — DASHBOARD_REDESIGN_AUDIT_REPORT_001.md written**
- `DASHBOARD_REDESIGN_LIVE_SMOKE_001`: **DONE — PASS (2026-04-09)**
- **REDESIGN FULLY COMPLETE — production-ready**
- Task board: `CLAUDE_TASK_BOARD.md` updated
