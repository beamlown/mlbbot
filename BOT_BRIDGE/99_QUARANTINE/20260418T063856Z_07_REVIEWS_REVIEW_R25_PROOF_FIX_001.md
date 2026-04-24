# REVIEW_R25_PROOF_FIX_001

Decision: APPROVED

## What passed
- **Scope**: only `dashboard_server.py` modified (inside `_read_state()` only). ✅
- **Bug proven before fix**: empty r25 samples returned zeroed metrics (win_rate=0) masking "no data" from "zero wins". ✅
- **Fix correct**: empty sample now returns win_rate=null, expectancy=null, sample_size=0. ✅
- **DB error fallback improved**: now returns null metrics + explicit error field instead of fake zero-performance sample. ✅
- **Loss counting corrected**: pnl <= 0 counts as loss (matches DASH_014 spec). ✅
- **No unrelated code changed**. ✅

## What failed
- None.

## Next action
- R25_PROOF_FIX_001 → DONE.
