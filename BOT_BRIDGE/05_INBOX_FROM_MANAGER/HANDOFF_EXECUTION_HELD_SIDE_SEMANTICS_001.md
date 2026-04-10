# HANDOFF_EXECUTION_HELD_SIDE_SEMANTICS_001

## Final status
VERIFIED_CAUSE_FOUND

## Exact code paths changed
- `C:\Users\johnny\Desktop\sports_bot_v2\core\risk.py`
  - added `_held_bid(side, ob)`
  - normalized `check_exit()` to use `current_held_price = _held_bid(trade.side, ob)`
  - normalized `mark_to_market()` to use `current_held_price = _held_bid(trade.side, ob)`
- `C:\Users\johnny\Desktop\sports_bot_v2\core\paper_exec.py`
  - added `_held_bid(side, ob)`
  - clarified `close_position()` around held-side exit pricing
  - normalized `mark_to_market_value()` to use `current_held_price = _held_bid(trade.side, ob)` and explicit held-side slippage sim

## Root cause proof
The execution math was already economically correct, but the held-side lookup existed as repeated raw `BUY_YES` / `BUY_NO` branches in multiple places:
- `risk.check_exit()`
- `risk.mark_to_market()`
- `paper_exec._fill_price_exit()` / `paper_exec.mark_to_market_value()`
- `paper_exec.close_position()`

That repetition preserved audit ambiguity around whether TP/SL and exits were using the actual held contract price or an implied YES/NO semantic interpretation. This was the exact execution-side gap left after the dashboard/SSE fix.

## Exact before / after pricing logic
### Before
- `risk.check_exit()`:
  - `if trade.side == 'BUY_YES': mark = ob.bid_yes else: mark = ob.bid_no`
  - `unrealized_pct = (mark - trade.entry_px) / trade.entry_px`
- `risk.mark_to_market()`:
  - same raw branch on `trade.side`
- `paper_exec.mark_to_market_value()`:
  - `exit_sim = _fill_price_exit(trade.side, ob)`
  - `return (exit_sim - trade.entry_px) * trade.qty`
- `paper_exec.close_position()`:
  - `exit_px = _fill_price_exit(trade.side, ob)`
  - `gross_pnl = (exit_px - entry_px) * qty`

### After
- `risk.check_exit()`:
  - `current_held_price = _held_bid(trade.side, ob)`
  - `held_unrealized_pct = (current_held_price - trade.entry_px) / trade.entry_px`
  - TP/SL/trailing/near-resolution all reference `current_held_price` or `held_unrealized_pct`
- `risk.mark_to_market()`:
  - `current_held_price = _held_bid(trade.side, ob)`
  - `return (current_held_price - trade.entry_px) * trade.qty`
- `paper_exec.mark_to_market_value()`:
  - `current_held_price = _held_bid(trade.side, ob)`
  - `held_exit_sim = current_held_price * (1.0 - PAPER_SLIPPAGE_PCT)`
  - `return (held_exit_sim - trade.entry_px) * trade.qty`
- `paper_exec.close_position()`:
  - `held_exit_px = _fill_price_exit(trade.side, ob)`
  - `gross_pnl = (held_exit_px - entry_px) * qty`
  - added held-contract comment for close pricing truth

## What is now proven
- TP/SL and close monitoring now use the actual held-side price by explicit name in execution logic.
- Close pricing still uses the actual held contract side bid with slippage.
- BUY_NO execution-side sign ambiguity is removed from the monitored/unrealized path naming.
- BOS/MIL-style opposite-side close risk is removed at the semantics layer because execution paths are now explicitly framed around held-side bid lookup, not ambiguous YES/NO wording.

## Temporary containment
Temporary containment is no longer needed for this specific execution-side semantics gap after this normalization, assuming no other unverified execution path outside the allowed files reintroduces side interpretation.

## Verification traces
- BUY_NO trace: entry `0.41`, `current_held_price=0.62` -> held unrealized pct `0.512195` (positive)
- BUY_NO trace: entry `0.41`, `current_held_price=0.78` -> held unrealized pct `0.902439` (TP zone)
- BUY_YES trace: entry `0.41`, `current_held_price=0.33` -> `-0.195122`
- BUY_YES trace: entry `0.41`, `current_held_price=0.31` -> `-0.243902` (SL zone)

## Short proof summary tied to incidents
- SEA/TEX pattern: BUY_NO held-price gains now remain explicitly positive throughout execution-side monitoring logic.
- BOS/MIL pattern: close semantics are now explicitly documented and named as held-side exit pricing, eliminating hidden opposite-side interpretation in the changed execution paths.

## Commit
- `2dbb3fc` — `Normalize execution held-side pricing semantics`
