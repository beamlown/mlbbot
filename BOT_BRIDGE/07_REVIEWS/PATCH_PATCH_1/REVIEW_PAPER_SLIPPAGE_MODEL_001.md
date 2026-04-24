# REVIEW — PAPER_SLIPPAGE_MODEL_001

Patch: PATCH_1 / step 3 of 10
Reviewer: patch-reviewer

## Scope check
Files changed per RESULT and verified on disk:
- `sports_bot_v2/core/types.py` — OBSnapshot gains `bid_levels_yes/no`, `ask_levels_yes/no`; Trade gains `actual_fill_px`. ✅ present (types.py:48–51, :136).
- `sports_bot_v2/core/orderbook.py` — populates the new level lists from CLOB. ✅ present (orderbook.py:150–173, :184–187, :215–218, :230–247).
- `sports_bot_v2/core/paper_exec.py` — adds `_walk_the_book`, `_get_fill_price_with_slippage`, `_fill_price_entry`, `_fill_price_exit`, toggles, logging, populates `actual_fill_px`. ✅ present.
- `sports_bot_v2/bot_core.py` — `PAPER_SLIPPAGE_ENABLED` / `PAPER_SLIPPAGE_CENTS` added to CONFIG_HASH inputs (:59–60) and /health gates (:381–382). ✅.

All changed files are inside the listed target set; no out-of-scope writes.

## Acceptance verification

### (1) Walk-the-book fill — **DEFECT**
The HANDOFF explicitly requires: *"Given an order side + desired size + current orderbook snapshot: compute volume-weighted average fill price by consuming liquidity from the opposite side"*.

On disk, `_fill_price_entry` and `_fill_price_exit` call `_walk_the_book` with a hardcoded `quantity_usd=1.0`:
- paper_exec.py:128 — `vwap, _, partial = _walk_the_book(side, 1.0, ask_levels)`
- paper_exec.py:172 — `vwap, _, partial = _walk_the_book(side, 1.0, bid_levels)`

Consequence: because Polymarket top-of-book levels almost always carry more than $1 of depth, the inner loop returns after consuming only the best level. The computed "VWAP" is effectively the best ask/bid, not a size-aware VWAP. The book is not actually walked for the real order size, and `partial_fill` can effectively never be True in production (requires <$1 of total book). This defeats the stated purpose of the task: edge measurements will remain optimistic at the sizes the bot trades (MIN_POSITION_USD=$10, MAX $50).

Ordering problem that caused this: `fill_px` is computed before `size_usd` in `open_position` (lines 202 vs 208–229), so the true dollar size isn't known when pricing. A correct fix needs either (a) decide size first then price, or (b) iterate/estimate — but the current code simply sidesteps the requirement.

### (2) Slippage buffer — OK
`_get_fill_price_with_slippage` adds `PAPER_SLIPPAGE_CENTS/100` on entry and subtracts on exit. Default 2.0¢. Configurable via env. Symmetric across BUY_YES/BUY_NO. ✅.

### (3) Toggle — OK
`PAPER_SLIPPAGE_ENABLED` short-circuits to best-quote behavior; also observed in `mark_to_market_value` (paper_exec.py:329–333). ✅.

### (4) Attribution field — OK
`Trade.actual_fill_px` added (types.py:136); populated in `open_position` (paper_exec.py:267) with the slippage-adjusted price. Contract for TRADE_ATTRIBUTION_WIRING_001 satisfied.

### (5) Logging — partial
Log lines at paper_exec.py:281–284 and :309–312 include side, size_usd (entry), qty, vwap, fill_px, slippage_bps, partial. Missing `desired_size`/`filled_size` distinction from the HANDOFF spec, but since walk-the-book is effectively neutered (defect 1), filled==desired always. Minor. `order_id` is not yet assigned at fill time (trade.id is None pre-DB-insert), acceptable given current flow.

## Example fills vs code behavior — **MISLEADING**
RESULT `example_fills` claims a medium-size order with `size_usd=146.05` consumes levels 1–3 and produces `vwap_without_slippage=0.54257`. With the code as written (`_walk_the_book(..., 1.0, ...)`), medium and large scenarios are not reproducible from the current implementation — they could only be produced by calling `_walk_the_book` with the intended size directly. The table describes the *designed* model, not the *shipped* model. Needs to be corrected or the code needs to pass real size.

## Config / drift
- `bot_core.py` CONFIG_HASH inputs include both new keys ✅ (bot_core.py:59–60).
- No change to decision logic, bankroll/sizing, live execution, or attribution schema. Honors "Do NOT do" list.

## Drift vs prior steps
- Step 1 dashboard parse-bug is unrelated to this task; no contact with dashboard HTML.
- Step 2 approved a single-source-of-truth cleanup; this patch doesn't touch paper_trades.db access paths.
- No cross-task contamination introduced.

## Secondary notes (non-blocking)
- `_walk_the_book` first arg `side` is unused; either wire it in or drop from signature.
- Empty-book fallback returns vwap=0.5, filled_usd=0.0, partial=True (paper_exec.py:55–56) — caller ignores the 0.5 via `if vwap <= 0: vwap = fallback_px`, but 0.5 is >0, so a truly empty book will mis-price at $0.50. Consider returning `0.0` or raising.
- `mark_to_market_value` applies slippage unconditionally on the held side (:332–333); fine for conservative paper MTM but worth documenting.

## Decision

DECISION: CHANGES_REQUESTED — walk-the-book is hardcoded to quantity_usd=1.0, so VWAP is computed for $1 not the real order size; requirement (1) and the RESULT's example table are not actually implemented.

TL;DR:
- Core defect: `_walk_the_book` is called with quantity_usd=1.0 at paper_exec.py:128 and :172, so the book is never actually walked at realistic trade sizes
- Slippage buffer, toggle, `actual_fill_px`, CONFIG_HASH wiring, and per-fill logging are all correctly implemented and in the right files
- RESULT `example_fills` table for medium/large sizes is not reproducible from the shipped code — it describes the design, not the behavior
- No drift from step 1 (dashboard JS parse bug) or step 2 (DB cleanup); scope guardrails respected
- Fix path: sequence size-before-price in `open_position`, pass real `size_usd` into `_fill_price_entry`, then re-run the 3-size verification table before re-submitting
