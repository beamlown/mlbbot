# REVIEW_DASHBOARD_REDESIGN_LIVE_SMOKE_001

Decision: **FAIL — CHANGES_REQUESTED**

Date: 2026-04-09
Commit claimed: a19f421

---

## Reason for FAIL

**BUY_NO unrealized P&L sign is wrong in the live running dashboard.** This is the same class of error as SEA/TEX and BOS/MIL. It was NOT closed by the redesign — it survived because the running `dashboard_server.py` process predates the `BASEBALL_POSITION_SEMANTICS_INCIDENT_001` fix and has never been restarted.

### Evidence

Live SSE captured from running server:
```
mlb-cin-mia-2026-04-09:
  current_price = 0.53
  live_equity_usd = 48.8299   → consistent: 92.131933 × 0.53 = 48.83 ✓
  unrealized_pnl_usd = +1.1701  → WRONG
```

Correct formula: `(current_price - entry_px) × qty = (0.53 - 0.5427) × 92.13 = -1.17`

Observed: `+1.1701`

The only formula that produces `+1.1701` from these numbers is `(entry_px - current_price) × qty = (0.5427 - 0.53) × 92.13 = +1.17`. This is the old BUY_NO sign-branched formula that `BASEBALL_POSITION_SEMANTICS_INCIDENT_001` was supposed to eliminate.

ARI/NYM reported by operator: entry 61.3¢, current 40.0¢ → old formula gives `(0.613 - 0.40) × 81.56 = +17.38`, which is what was observed (+$17.38 shown, -$17.38 correct).

### Root Cause

The on-disk `dashboard_server.py` at line 420 reads:
```python
unrealized_pnl_usd = round((current_price - entry_px) * qty, 4)
```
This is correct (no side branching). But the **running process was started before this fix was committed** and still has the old sign-branched code in memory. No code restart has occurred since `BASEBALL_POSITION_SEMANTICS_INCIDENT_001` was merged.

Fix required: restart the `dashboard_server` process so it loads the fixed code from disk. No code changes needed.

### Inconsistency in SSE also explains CIN/MIA discrepancy from prior session

Earlier session noted: `current_price=0.54` with `unrealized=+0.2488`. This was also the sign bug — old formula `(0.5427 - 0.54) × 92.13 = +0.2488`. Not a stale-data artifact as incorrectly noted in the previous review version.

---

## What passed (unchanged)

- Server HTTP 200 ✓
- `/api/state` fields present ✓
- `/api/trades` TP/SL math correct (server-side function, reads on each call) ✓
- Shadow absent from LIVE tab HTML ✓
- Advisory label correct in GAMES tab ✓
- Flicker eliminated (dashboard.html Phase 4) ✓
- Frontend code: `buildUnifiedPositionCards` and `_applyMarkToCard` both use `unrealized_pnl_usd` from SSE without sign modification ✓ — the frontend is correct; it faithfully renders whatever the server sends

## What failed

| Check | Result |
|---|---|
| BUY_NO unrealized P&L sign | **FAIL** — server sends `+1.17` where `-1.17` is correct |
| ARI/NYM operator-reported sign | **FAIL** — `+$17.38` shown, `-$17.38` correct |
| Truth model: no sign branching at server | **FAIL** — running process still has old sign-branched formula |

## Required action

1. Restart the `dashboard_server.py` process (kill and relaunch via `launch_all.py` or directly)
2. Verify SSE sends `-1.17` for CIN/MIA BUY_NO with current=0.53
3. Verify LIVE card shows `-$17.38` style for ARI/NYM BUY_NO when stream has price below entry

Track as: **LIVE_CARD_PNL_SIGN_REGRESSION_001**
