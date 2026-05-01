# REVIEW — BANKROLL_AWARE_SIZING_001
**Date:** 2026-04-10
**Verdict:** APPROVED

## Scope check
- Files changed: `core/paper_exec.py`, `.env` only — matches allowed_files exactly
- No forbidden files touched

## Acceptance criteria
| Criterion | Result |
|---|---|
| MAX_POSITION_SIZE_USD in .env = 50 | PASS |
| RISK_PCT_PER_TRADE and MIN_POSITION_USD present in .env | PASS |
| paper_exec.py reads current bankroll from STARTING_BANKROLL + total_realized_pnl() | PASS |
| Bankroll-aware base: max(MIN_POSITION_USD, bankroll * RISK_PCT_PER_TRADE) | PASS |
| Confidence tier multiplier still applied | PASS — _confidence_size() called with bankroll_base |
| Result clamped to [MIN_POSITION_USD, MAX_POSITION_SIZE_USD=50] | PASS — _confidence_size() enforces MAX_POSITION_SIZE_USD |
| recommended_size_dollars override path preserved and capped at 50 | PASS |
| DB read failure falls back to PAPER_POSITION_SIZE_USD with WARNING | PASS |
| INFO log emitted on each sizing computation | PASS |
| py_compile passes | PASS |

## Worked example at current bankroll
- bankroll=$851.91, conf=0.72 → base=$25.56 × 1.25 = $31.95 (well below $50 cap)
- Drawdown to $333: base=$10.00 (floor) → $12.50 high tier → $15.00 very high

## Restart required: YES
