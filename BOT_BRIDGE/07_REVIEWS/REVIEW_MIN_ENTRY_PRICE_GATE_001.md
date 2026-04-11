# REVIEW_MIN_ENTRY_PRICE_GATE_001.md

## Verdict
APPROVED

## Decision
Approve `MIN_ENTRY_PRICE_GATE_001`.

## Why
- Worker stayed within allowed scope.
- Only `core/risk.py` was modified.
- The patch is the correct minimal response to the approved audit finding:
  ultra-low-price entries were entering at 0.05–0.07 and stopping out almost immediately because spread alone exceeded the stop threshold.
- The new gate uses the correct side-specific ask:
  - `ob.ask_yes` for `BUY_YES`
  - `ob.ask_no` for `BUY_NO`
- `python -m py_compile core/risk.py` passed.

## What changed
- Added a minimum entry price gate in `check_entry_gates()`
- Default threshold is `0.15`
- Reject reason follows the intended pattern:
  `entry_price_too_low:{ask_side:.4f}<{MIN_ENTRY_PRICE:.4f}`

## Runtime note
- Restart is required before this fix is live.

## Manager judgment
Close `MIN_ENTRY_PRICE_GATE_001` to DONE.
Promote the next queued risk task:
`TP_NEAR_RESOLUTION_CAP_FIX_001`
