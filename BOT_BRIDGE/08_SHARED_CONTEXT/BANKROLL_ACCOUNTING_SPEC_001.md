# Paper Accounting Spec — sports_bot_v2 (Canonical)

**Document**: BANKROLL_ACCOUNTING_SPEC_001.md  
**Date**: 2026-04-17  
**Status**: LIVE (post-fix)  
**Audit Task**: BANKROLL_SESSION_RULES_001  

---

## Overview

This document defines the authoritative accounting formulas and invariants for paper trading state in sports_bot_v2. All money-flow calculations in the dashboard and paper execution engine must satisfy these invariants.

---

## Invariant I1: Available Cash

**Definition:**  
`available_cash = bankroll_usd - total_committed_usd`

**Where:**
- `bankroll_usd` = `STARTING_BANKROLL + sum(pnl_usd for all closed trades)`
- `total_committed_usd` = `sum(entry_px * qty + fees_usd for all OPEN positions)`

**Location:**  
`dashboard_server.py`, function `_read_state()`, line 542:
```python
"available_cash": round(max(0.0, current - acct["capital_committed"]), 2),
```

**Status**: ✓ CONFIRMED  
No changes required. Formula is correct.

---

## Invariant I2: Live Equity Uses Held-Side Bid Price

**Definition:**  
Open position mark-to-market value must equal `qty * held_side_bid_price`, where:
- For `BUY_YES`: use `bid_yes`
- For `BUY_NO`: use `bid_no`

**Relationship to Unrealized PnL:**  
`live_equity_usd = entry_px * qty + unrealized_pnl_usd`
`unrealized_pnl_usd = (held_side_bid - entry_px) * qty`
Therefore: `live_equity_usd = qty * held_side_bid`

**Location:**  
`dashboard_server.py`, function `_stream_positions_mark()`, lines 474–483.

**Changes Made (2026-04-17):**  
Fixed to use `best_bid` consistently instead of `current_price`:

```python
# AFTER (CORRECT):
best_bid = mark.get("best_bid")
if best_bid is not None:
    best_bid = float(best_bid)
    live_equity_usd = round(qty * best_bid, 4)
    unrealized_pnl_usd = round((best_bid - entry_px) * qty, 4)
    live_equity_total += live_equity_usd
```

**Bug Fixed:**
1. Used `current_price` instead of `best_bid` (incorrect mark source)
2. Added to total even when `best_bid` was None (inconsistent with unrealized_pnl)

**Status**: ✓ FIXED  
Changed lines: 474–483 of `dashboard_server.py`

---

## Invariant I3: Session PnL Anchors Correctly

**Definition:**  
`session_pnl = sum(pnl_usd for all closed trades where ts_close >= session_start_ts)`

Session PnL must use a fixed session_start_ts that persists across restarts.

**Location:**  
`dashboard_server.py`, lines 528–536

**Verification (2026-04-17):**
- Closed trades in session: 276 of 277
- Session PnL from query: `-91.1263`
- Matches state.json: ✓ Yes

**Status**: ✓ CONFIRMED  
No changes required.

---

## Invariant I4: Lifetime Realized PnL Accumulates Correctly

**Definition:**  
`lifetime_realized_pnl = sum(pnl_usd for all trades where status='closed')`

**Verification (2026-04-17):**
- DB query sum: `-91.1263`
- state.json `pnl.realized`: `-91.1263`
- Match: ✓ Yes

**Status**: ✓ CONFIRMED  
No changes required.

---

## Invariant I5: No Double-Counting Between Open and Realized

**Definition:**  
Closed trades must not appear in open position accounting. Separation enforced at query level.

**Status**: ✓ CONFIRMED  
No changes required.

---

## Summary

### Changes
- **`dashboard_server.py`** lines 474–483: Fixed I2 (use `best_bid` for mark-to-market)

### Verdicts
- I1 (available_cash): ✓ CONFIRMED
- I2 (live_equity bid): ✓ FIXED
- I3 (session anchor): ✓ CONFIRMED
- I4 (lifetime pnl): ✓ CONFIRMED
- I5 (no double-count): ✓ CONFIRMED
