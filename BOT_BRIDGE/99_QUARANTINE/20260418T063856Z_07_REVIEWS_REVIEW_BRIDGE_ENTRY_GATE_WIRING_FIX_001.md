# REVIEW — BRIDGE_ENTRY_GATE_WIRING_FIX_001
**Reviewed by:** Claude (manager)
**Date:** 2026-04-10
**Verdict:** APPROVED — restart required to activate

---

## Summary

Patched `bot_core.py` bridge entry section to call `check_entry_gates()` between `Signal()` construction and `open_position()`. 14 lines inserted, 0 lines removed from surrounding logic. Minimal, local change.

---

## Acceptance Criteria Check

| Criterion | Result |
|-----------|--------|
| Bridge path calls check_entry_gates() before open_position() | PASS — lines 507–517 |
| Rejected entries do not reach open_position() | PASS — `continue` on line 525 |
| Rejection reasons logged clearly | PASS — `BRIDGE GATE REJECT [check_entry_gates] slug=... reasons=...` |
| Passing entries still open normally | PASS — `open_position()` at line 526 unchanged |
| No files outside allowed scope modified | PASS — bot_core.py only |
| py_compile passes | PASS — confirmed |

---

## Call Order Verification

```
Signal() construction   ← line 475–503
build _bridge_open_per_market from current_open   ← lines 504–506 (NEW)
check_entry_gates(ob, signal, mode_ctx, ...)     ← lines 507–517 (NEW)
  if not _gate_ok: log + _guard_block_count++ + continue  ← lines 518–525 (NEW)
open_position()         ← line 526 (only reached if gate passes)
insert_open_trade()     ← line 533
```

Order is correct. Gate is gating.

---

## Variables In Scope Check

All required arguments to `check_entry_gates()` confirmed available at insertion point:
- `ob` — from `get_orderbook_snapshot(market)` called 3 lines before insertion
- `signal` — constructed immediately before insertion
- `mode_ctx` — set at top of main loop iteration
- `len(current_open)` — `current_open = fetch_open_trades()` called at start of each bridge intent iteration
- `_bridge_open_per_market` — freshly built from `current_open` in the new lines
- `market.market_id` — market resolved from slug lookup
- `_time_to_end(market)` — function defined in bot_core.py, in scope
- `market=market` — in scope
- `market_cooldown=_market_cooldown` — module-level dict, in scope throughout `main()`

---

## Guard Accounting

On rejection: `_guard_block_count` incremented and `loop_guard_reasons` updated — consistent with how other blocks in the loop track guard events. This feeds into the `guard_block_rate` metric in `/api/state`.

---

## Minor Notes (non-blocking)

- `_time_to_end(market)` is called fresh at gate time. If the gate fires the `too_close_to_end` check, that same `_time_to_end` call result is used. Minor extra computation vs storing it earlier — acceptable, not a bug.
- `_bridge_open_per_market` is built from `current_open`, which is a fresh fetch at the start of each bridge intent iteration. This gives accurate per-market count for the gate. Correct.

---

## What This Fix Changes in Practice

After restart:
- `MIN_ENTRY_CONFIDENCE=0.60` will actually gate bridge entries — signals with confidence < 0.60 will be logged as `BRIDGE GATE REJECT [check_entry_gates]` and not reach `open_position()`
- `MAX_TOTAL_COMMITTED_USD=150` exposure cap applies to bridge entries
- Spread, depth, imbalance, concurrent, per-market, cooldown gates all apply

---

## Restart Required

**Yes.** `bot_core.py` is a running live process. The patch is a source-file change only. The live process must be restarted before the fix is active. Until restart, bridge entries continue to bypass the gate.

---

## Decision

**APPROVED** — minimal correct patch, all acceptance criteria met, py_compile clean. Restart required to activate. Post-fix runtime verification recommended (CONFIDENCE_GATE_POSTFIX_VERIFY_001).
