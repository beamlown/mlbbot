# PROVISIONAL_REVIEW_EXECUTION_HELD_SIDE_SEMANTICS_001

## Status
VERIFIED_CAUSE_FOUND

## Scope respected
Only these allowed files were changed:
- `C:\Users\johnny\Desktop\sports_bot_v2\core\risk.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\core\paper_exec.py`

## Exact execution paths inspected and normalized
- `core.risk.check_exit()`
- `core.risk.mark_to_market()`
- `core.paper_exec.mark_to_market_value()`
- `core.paper_exec.close_position()`

## Exact fix point
A canonical held-side bid helper now exists in both execution files:
- `def _held_bid(side: str, ob: OBSnapshot) -> float | None:`
- `return ob.bid_yes if side == 'BUY_YES' else ob.bid_no`

## TP/SL / close proof
`check_exit()` now computes:
- `current_held_price = _held_bid(trade.side, ob)`
- `held_unrealized_pct = (current_held_price - trade.entry_px) / trade.entry_px`

This means TP, SL, gap stop, trailing stop, and near-resolution all reference the actual held contract price by explicit name.

`close_position()` still exits using the held-side bid with slippage:
- `held_exit_px = _fill_price_exit(trade.side, ob)`
- `gross_pnl = (held_exit_px - entry_px) * qty`

## Incident-pattern proof
- SEA/TEX BUY_NO pattern: if the held NO bid rises above entry, execution-side unrealized is explicitly positive.
- BOS/MIL pattern: changed paths now describe and compute close pricing as held-side exit pricing, removing opposite-side wording ambiguity.

## Temporary containment
No longer needed for this specific execution semantics gap after the normalization and verification traces.

## Commit
- `2dbb3fc` — `Normalize execution held-side pricing semantics`
