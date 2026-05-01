# REVIEW — DASHBOARD_TRUTH_REVERIFY_001
**Date:** 2026-04-10
**Verdict:** CHANGES_REQUESTED

## Scope check
- All 4 allowed files read: confirmed
- All 7 display areas evaluated: confirmed
- No code modified: confirmed
- Result written to correct outbox path: confirmed

## Display area verdicts
| Area | Verdict | Notes |
|---|---|---|
| 1. Open positions panel | PASS | DB=0, API=0, UI=0 — all aligned |
| 2. Bankroll/accounting strip | PASS | available_cash, committed, live equity internally consistent at zero-open state |
| 3. PnL fields | **FAIL** | Positions tab "Realized P&L" shows +$43.62 (slice sum) — true realized is +$405.89 |
| 4. r25 win rate | PASS | UI 52% matches API and DB recompute exactly |
| 5. Position card sign semantics (BUY_YES/BUY_NO) | UNVERIFIED | No open positions at audit time — cannot verify |
| 6. Game feed / status labels | PASS | UI matches /api/games status semantics |
| 7. Mark source display | **FAIL** | Backend emits mark_source but live cards do not render it |

## Additional finding
| Severity | Finding | Fix scope |
|---|---|---|
| MEDIUM | R25 tile sublabel shows "0 trades" — reads s.total_closed which is absent in /api/state | dashboard.html line ~683 |

## Required fixes before this task can close
Three items in `dashboard.html` only:

### Fix 1 — Positions tab Realized P&L mis-sourced (FAIL)
- **File:** `dashboard.html` lines 1342-1351
- **Problem:** `renderPositionsTab` computes `todayRealized` by summing sliced/visible closed trades — produces an arbitrary partial sum, not total realized P&L
- **Fix:** Replace closed-slice reduction with authoritative value from `/api/state pnl.realized` or `/api/bankroll net_pnl`. If intentionally showing a recent-only metric, relabel it clearly (e.g. "Recent P&L") so it is not confused with total realized.

### Fix 2 — mark_source not displayed on position cards (FAIL)
- **File:** `dashboard.html` lines 1021-1031 and 906-982
- **Problem:** `buildUnifiedPositionCards` stores `mark_source` on position objects but never surfaces it in the card UI. The source chip shows trade source (model_bridge/manual), not mark source (stream/rest_fallback/poll_fallback).
- **Fix:** Add `mark_source` indicator to card metadata area or stale badge so REST fallback visibility is explicit to the operator.

### Fix 3 — R25 tile sublabel reads zero (ADDITIONAL/MEDIUM)
- **File:** `dashboard.html` line ~683
- **Problem:** UI reads `s.total_closed ?? 0` but `/api/state` exposes `total_trades` and `r25.sample_size`, not `total_closed`
- **Fix:** Substitute `s.r25?.sample_size` or `s.total_trades` as appropriate for the intended label.

## Unverified item — requires follow-up
- **Area 5 (BUY_YES/BUY_NO position card sign semantics):** Cannot be verified without active open positions. Must be re-checked during a session with at least one open BUY_YES and one open BUY_NO card. A lightweight re-smoke task should be queued after the fixes are applied.

## Follow-on task
`TASK_DASHBOARD_TRUTH_FIXES_001` has been written to the inbox. It is scoped to `dashboard.html` only, targeting the exact lines above.

## Rollback
N/A — read-only task, no changes made.
