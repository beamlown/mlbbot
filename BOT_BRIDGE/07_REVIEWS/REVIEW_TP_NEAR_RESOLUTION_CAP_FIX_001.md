# REVIEW_TP_NEAR_RESOLUTION_CAP_FIX_001.md

## Verdict
APPROVED

## Decision
Approve `TP_NEAR_RESOLUTION_CAP_FIX_001`.

## Why
- Worker stayed within allowed scope.
- Only `core/risk.py` was modified.
- The patch directly addresses the approved audit finding that near-1.0 entries could compute unreachable take-profit values above the meaningful ceiling of a 0–1 contract.
- The worker applied the cap directly in `get_tp_price(trade)`.
- `python -m py_compile core/risk.py` passed.

## What changed
- `core/risk.py`
- TP is now capped at the near-resolution ceiling so near-1.0 entries cannot compute unreachable TP values above the meaningful contract upper bound.
- Normal TP behavior for ordinary entries remains intact below the cap.

## Runtime note
- Restart is required before this fix is live.

## Manager judgment
Close `TP_NEAR_RESOLUTION_CAP_FIX_001` to DONE.
