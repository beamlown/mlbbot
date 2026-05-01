# REVIEW_LIVE_CARD_PNL_SIGN_REGRESSION_001

Decision: **APPROVED (PASS)**

Date: 2026-04-09

---

## Fix applied

- Killed stale PID 35892 (pre-fix in-memory code)
- Started fresh PID 43288 from `sports_bot_v2/dashboard_server.py`
- No code changes — on-disk file was already correct

## Before / after proof

| Slug | Side | Entry | Current | Before SSE PnL | After SSE PnL | Correct | Sign |
|---|---|---|---|---|---|---|---|
| mlb-cin-mia-2026-04-09 | BUY_NO | 0.5427 | 0.63 | -8.04 ❌ | **+8.04** | +8.04 | **PASS** |
| mlb-ari-nym-2026-04-09 | BUY_NO | 0.613 | 0.40 | +17.38 ❌ | **-17.38** | -17.38 | **PASS** |
| mlb-oak-nyy-2026-04-09 | BUY_YES | 0.352 | 0.63 | — | +39.55 | +39.55 | **PASS** |

ARI/NYM is the exact operator-reported regression case: entry 61.3¢, current 40.0¢ now correctly shows **-$17.38**.

## Acceptance criteria

| Criterion | Status |
|---|---|
| BUY_NO non-null current_price found | PASS |
| Sign correct for losing BUY_NO (current < entry) | PASS |
| Sign correct for winning BUY_NO (current > entry) | PASS |
| live_equity_usd internally consistent for all positions | PASS |
| No new truth regression introduced | PASS |
| No production code changed | PASS |

## Incident closure

**ARI/NYM sign regression: CLOSED.** Running process now uses `(current_price - entry_px) × qty` with no side branching. Cannot recur as long as the process is not replaced by a pre-fix binary.

## Next

Dashboard redesign smoke test (`DASHBOARD_REDESIGN_LIVE_SMOKE_001`) may now be re-run to close the redesign as fully complete.
