# BANKROLL_ACCOUNTING_SPEC_001

**Canonical Paper Trading Accounting Formulas**
Post-audit document for TASK_BANKROLL_SESSION_RULES_001.

---

## Invariant I1: available_cash Formula

```
available_cash = current_bankroll - total_committed_usd
```

Where:
- `current_bankroll = STARTING_BANKROLL + realized_pnl`
- `total_committed_usd = SUM(entry_px * qty + fees_usd) for all OPEN trades`

**Implementation**: `dashboard_server.py:_read_state()` line 543.

**Key Detail**: Entry fees (paid when opening) are included in committed amount. Exit fees are already absorbed in `realized_pnl` for closed trades.

---

## Invariant I2: live_equity Mark-to-Market Formula

```
unrealized_pnl = (held_side_bid - entry_px) * qty
```

Where:
- `held_side_bid` = `bid_yes` for BUY_YES, `bid_no` for BUY_NO
- **Never use ask price, mid price, or entry price for mark-to-market**

**Implementation**:
- `core/paper_exec.py:mark_to_market_value()` (lines 173-181) — correct, uses `_held_bid()`
- `dashboard_server.py:_stream_positions_mark()` (lines 474-480) — uses best_bid from market mark; None if bid unavailable

---

## Invariant I3: session_pnl Anchoring

```
session_pnl = SUM(pnl_usd) for all CLOSED trades WHERE ts_close >= session_start_ts
```

**Implementation**: `dashboard_server.py:_read_state()` line 533.
**Status**: Anchors correctly to `state.json:pnl.session_start_ts`; does not reset on process restart.

---

## Invariant I4: lifetime realized_pnl

```
realized_pnl = SUM(pnl_usd) for all CLOSED trades (no time filter)
```

**Implementation**:
- `state.json:pnl.realized` — source of truth
- Dashboard API endpoint `/api/bankroll` queries DB: `SUM(pnl_usd) WHERE status='closed'`

**Data Consistency**: DB query must equal `state.json:pnl.realized` value. Currently: -91.1263 ✓

---

## Invariant I5: No Double-Counting

**Separation Confirmed**:
- Open positions: counted in `_compute_open_trade_accounting()` WHERE `status='open'`
- Realized PnL: counted WHERE `status='closed'`
- Closed trades do not appear in open equity calculations ✓

---

## Trade Lifecycle Accounting

### Open Position
- SQL: INSERT with `status='open'`, `entry_px`, `qty`, `fees_usd` (entry fees only)
- Committed: `entry_px * qty + fees_usd`
- Mark-to-market: `(held_side_bid - entry_px) * qty`

### Close Position
- SQL: UPDATE with `status='closed'`, `exit_px`, `pnl_usd`, `ts_close`
- `pnl_usd = (exit_px - entry_px) * qty - entry_fees - exit_fees`
- Realized PnL accumulates to state and DB

---

## Fixes Applied in Task

1. **I1 Fix**: Added `fees_usd` to `_compute_open_trade_accounting()` SQL query and summation
2. **I2 Fix**: Changed `_stream_positions_mark()` to use `best_bid` for unrealized PnL instead of `current_price`
3. Removed dead `available_cash` calculation from `_compute_open_trade_accounting()`; actual available_cash computed in `_read_state()`

---

**Audit Date**: 2026-04-17  
**Status**: All 5 invariants confirmed or fixed ✓
