# REVIEW_BASEBALL_POSITION_SEMANTICS_INCIDENT_001

Decision: APPROVED

## What passed
- **Scope**: `dashboard_server.py` modified (SSE `_stream_positions_mark` function) — appropriate for a dashboard math fix. ✅
- **Root cause correctly identified**: `_stream_positions_mark` previously special-cased BUY_NO unrealized PnL as `(entry_px - current_price) * qty` while computing `live_equity` as `qty * current_price`. The sign inversion on unrealized was inconsistent with the equity formula. ✅
- **Fix correct**: removed BUY_NO special-case sign inversion — all positions (YES and NO) now use one held-contract formula: `live_equity = current_price * qty`, `unrealized = live_equity - committed`. ✅
- **Minimum fix applied**: no unrelated code changed, no dashboard.html changes beyond scope. ✅
- **Live proof**: after fix, open-position SSE/dashboard math uses same current held price for both live_equity and unrealized. For SEA/TEX BUY_NO, rising NO contract price now shows both higher equity and positive unrealized — previously they had opposite signs. ✅
- **Two affected trades identified**: id=160 (MIL/BOS BUY_YES) and id=166 (SEA/TEX BUY_NO) — correctly traced. ✅
- **Rollback**: revert `dashboard_server.py`. ✅

## What failed
- None.

## Notes
- The result flags `tp_sl_or_close_inherited_bug: true` — TP/SL and close pricing may have related semantic issues inherited from the same wrong formula. This may warrant a follow-up audit if positions are not closing at expected prices.
- The BOS/MIL (id=160) incident was a separate but related family: wrong held-side team semantics in close pricing interpretation, now fixed as part of this same pass.

## Next action
- BASEBALL_POSITION_SEMANTICS_INCIDENT_001 → DONE.
- Watch for TP/SL close price accuracy on next live session; if incorrect, a follow-up task may be needed.
