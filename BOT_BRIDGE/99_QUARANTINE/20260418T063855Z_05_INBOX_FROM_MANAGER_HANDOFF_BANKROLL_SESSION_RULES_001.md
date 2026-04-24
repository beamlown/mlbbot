# HANDOFF: BANKROLL_SESSION_RULES_001

## Status: QUEUED — activate after TRADE_FORENSICS_SNAPSHOT_001 completes (paper_exec.py conflict)

**Title**: Paper accounting correctness audit and fix
**Priority**: HIGH
**Subsystem**: accounting / bankroll
**Issued**: 2026-04-17
**Assigned**: SONNET_WORKER

---

## What this task is

Audit and fix paper trading accounting correctness in `dashboard_server.py` and `core/paper_exec.py`. The goal is to confirm (or fix) five accounting invariants so the dashboard shows true performance numbers.

The sizing rules audit (SIZING_RULES_SPEC_001) identified two HIGH gaps (GAP-1: no per-session USD cap; GAP-2: bankroll-agnostic sizing). Both were subsequently addressed by SESSION_EXPOSURE_CAP_001 and BANKROLL_AWARE_SIZING_001. This task is NOT about sizing — it is about whether the accounting layer correctly computes and surfaces what has happened.

---

## The 5 invariants you must confirm or fix

**I1 — available_cash is correct**
`available_cash` in the dashboard must equal `bankroll_usd - total_committed_usd` where `total_committed_usd` is the sum of `committed_usd` for all currently OPEN positions. If the formula is wrong or the source data is wrong, fix it.

**I2 — live_equity uses held-side bid price only**
Open position mark-to-market value must use the **bid price of the held side** (bid_yes for BUY_YES, bid_no for BUY_NO), not ask price, not mid, not the entry price. Confirm the mark source is correct in both dashboard_server.py and paper_exec.py.

**I3 — session PnL anchors correctly**
Session PnL must compute from a fixed session_start_ts, not reset on process restart. SESSION_PNL_TRUE_START_FIX_001 (APPROVED 2026-04-11) addressed this — confirm it is working correctly, or fix if not.

**I4 — lifetime realized PnL accumulates correctly**
Lifetime realized PnL = sum of `pnl_usd` for all CLOSED trades. Confirm this is what `state.pnl.realized` reflects and what the dashboard shows. Cross-check against DB query.

**I5 — no double-counting between open equity and realized**
Open position mark value and realized PnL must be cleanly separated. Closed trades must not appear in open equity. Confirm.

---

## How to approach this

1. Read `core/paper_exec.py` to trace how `committed_usd`, `pnl_usd`, and position lifecycle writes work
2. Read `dashboard_server.py` to trace how `available_cash`, `live_equity`, `realized_pnl`, and `session_pnl` are computed
3. Check `runtime/state.json` to see what PnL fields are currently written
4. For each invariant: read the code, state "CONFIRMED" or "BUG FOUND: <description>", then fix if bug found

---

## Deliver back

- Result JSON with verdict per invariant (CONFIRMED or FIXED)
- If fixed: exact lines changed, py_compile result for each modified file
- BANKROLL_ACCOUNTING_SPEC_001.md written to `BOT_BRIDGE/08_SHARED_CONTEXT/` documenting the canonical accounting formulas as they exist post-fix

## Allowed files

- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\core\paper_exec.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\runtime\state.json` (read-only)
- `C:\Users\johnny\Desktop\sports_bot_v2\trades_sports.db` (SELECT only)
- `C:\Users\johnny\Desktop\BOT_BRIDGE\08_SHARED_CONTEXT\BANKROLL_ACCOUNTING_SPEC_001.md` (write — create this)

## Do not touch

- `bot_core.py`
- `core/risk.py`
- `dashboard.html`
- Any mlb_model file
- Any file not listed above
