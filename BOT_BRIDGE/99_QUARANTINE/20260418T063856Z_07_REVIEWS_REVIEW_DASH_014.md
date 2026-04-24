# REVIEW_DASH_014

Decision: APPROVED

## What passed

- **Scope**: only `dashboard_server.py` modified — matches allowed_files exactly. ✅
- **ENV reads at module level** (lines 50-51): `AUTO_TAKE_PROFIT_PCT` and `AUTO_STOP_LOSS_PCT` added with correct defaults (0.85, 0.20). ✅
- **Side-aware TP/SL in _fetch_trades()** (lines 252-257):
  ```python
  if side == "BUY_NO":
      tp_price = max(0.01, 1.0 - entry_px * (1 + AUTO_TAKE_PROFIT_PCT))
      sl_price = min(0.99, entry_px * (1 + AUTO_STOP_LOSS_PCT))
  else:
      tp_price = min(0.99, entry_px * (1 + AUTO_TAKE_PROFIT_PCT))
      sl_price = max(0.01, entry_px * (1 - AUTO_STOP_LOSS_PCT))
  ```
  BUY_NO TP now correctly produces a low YES price (e.g. entry=0.41 → tp=0.241). Old hardcoded 0.85 gone. ✅
- **r25 block in _read_state()** (lines 314-334): Queries last 25 closed trades, computes win_rate, wins, losses, expectancy, sample_size. Attached to `state["r25"]`. Includes a try/except fallback returning zeroed r25 on DB error — safe. Minor note: worker uses `>0`/`<0` split so breakeven trades ($0.00 pnl) count as losses; this is acceptable and consistent. ✅
- **Rollback**: `dashboard_server.py` only — revertable. ✅

## What failed

- None.

## Next action

DASH_015 and RISK_001 also complete. Promote DASH_016 to ACTIVE.
