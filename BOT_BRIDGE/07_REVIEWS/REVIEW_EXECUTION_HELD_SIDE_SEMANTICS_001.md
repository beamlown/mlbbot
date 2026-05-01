# REVIEW_EXECUTION_HELD_SIDE_SEMANTICS_001

Decision: APPROVED

## What passed

- **Scope**: only `core/risk.py` and `core/paper_exec.py` modified — both in allowed_files. ✅
- **`_held_bid()` added to both files**: `return ob.bid_yes if side == 'BUY_YES' else ob.bid_no` — single canonical source for held-contract mark. ✅
- **`check_exit()` normalized**: raw `if BUY_YES: mark = ob.bid_yes else: mark = ob.bid_no` replaced with `current_held_price = _held_bid(trade.side, ob)`. ✅
- **`mark_to_market()` normalized**: same pattern, explicit `current_held_price` naming. ✅
- **`mark_to_market_value()` in paper_exec normalized**: replaces implicit `_fill_price_exit()` call with explicit `current_held_price = _held_bid()` + inline slippage. ✅
- **`close_position()` clarified**: `exit_px` renamed to `held_exit_px` — held-side exit explicitly named. ✅
- **No formula changes**: math identical before and after — confirmed by before/after diff in result. ✅
- **No other files modified**: `bot_core.py`, `dashboard_server.py`, `dashboard.html`, `core/db.py`, `core/model_bridge.py`, `mlb_model/` untouched. ✅

## Verification traces — all exact

| Trace | Expected | Reported | Pass |
|-------|----------|----------|------|
| BUY_NO bid_no=0.62, entry=0.41 | (0.62-0.41)/0.41 = +0.51220 | 0.512195 | ✅ |
| BUY_NO TP bid_no=0.78, entry=0.41 | (0.78-0.41)/0.41 = +0.90244 → TP fires | 0.902439 | ✅ |
| BUY_YES loss bid_yes=0.33, entry=0.41 | (0.33-0.41)/0.41 = -0.19512 → no SL | -0.195122 | ✅ |
| BUY_YES SL bid_yes=0.31, entry=0.41 | (0.31-0.41)/0.41 = -0.24390 → SL fires | -0.243902 | ✅ |

## Incident closure

- **SEA/TEX BUY_NO sign inconsistency (execution side)**: CLOSED. `check_exit()` now uses `current_held_price = bid_no` for BUY_NO trades. Positive unrealized when NO contract gains value. ✅
- **BOS/MIL opposite-side close ambiguity**: CLOSED. `close_position()` now explicitly uses `held_exit_px` from `_fill_price_exit(trade.side, ob)` — held side is canonical. ✅
- **Temporary containment**: worker confirmed `temporary_containment_remains_needed = false`. ✅

## Rollback

Revert `core/risk.py` and `core/paper_exec.py`. Commit `2dbb3fc`. No DB or schema changes to revert.

## Next action

- EXECUTION_HELD_SIDE_SEMANTICS_001 → DONE
- Redesign gate: CLEARED — promote DASHBOARD_REDESIGN_ARCH_001 to ACTIVE
