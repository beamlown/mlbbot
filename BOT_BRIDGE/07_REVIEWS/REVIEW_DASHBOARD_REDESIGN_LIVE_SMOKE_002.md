# REVIEW_DASHBOARD_REDESIGN_LIVE_SMOKE_002

Decision: **CHANGES_REQUESTED**

Date: 2026-04-09

---

## Summary

Dashboard is up, all API checks pass, all 5 tabs present, TP/SL semantics correct for BUY_NO, GAMES advisory label confirmed. One genuine blocker prevents APPROVED: sign formula could not be re-verified against a non-null live price. A second reported blocker (#shadow-feed) is a false negative — criterion is met.

---

## Acceptance criteria status

| Criterion | Status | Notes |
|---|---|---|
| HTTP 200 from localhost:8900 | PASS | ✓ |
| /api/state returns bankroll, r25 win_rate, bridge_enabled | PASS | ✓ |
| /api/trades returns open positions with side-correct TP/SL | PASS | BUY_NO: tp=0.01 (low YES price), sl=0.73566 ✓ |
| SSE BUY_NO sign formula `(current_price - entry_px) * qty` | BLOCKED | ARI/NYM only open position — current_price=null (stale mark). Formula cannot be exercised. |
| SSE live_equity_usd and unrealized_pnl_usd internally consistent | BLOCKED | Null mark; both fields null. Cannot verify. |
| Shadow absent from LIVE tab: #shadow-feed not in tab-live HTML | PASS | `#shadow-feed` is in `#drawer > #tab-shadow` (line 537). It is NOT inside `#tab-live` (lines 410–457). Worker checked page-wide presence — incorrect reading of criterion. |
| Advisory label in GAMES tab: 'Shadow Advisory — Not Executed' | PASS | ✓ confirmed in HTML |
| No new sign regression | PASS | No regression introduced. PID 43288 still running correct formula. |
| All tabs present: LIVE, POSITIONS, GAMES, HISTORY, SYSTEM | PASS | ✓ all 5 confirmed |

---

## Real blocking issue

**SSE sign verification — null current_price.**

ARI/NYM is the sole open position. Its NO token mark went stale (mark_age ≈ 238s) because the Polymarket WebSocket only sends delta events and ARI/NYM is SCHEDULED (pre-game, no active trading). After two reconnects, Polymarket did not push a current price on re-subscription. `state_hub.snapshot()` returned `current_price=null` → `unrealized_pnl_usd=null` → formula cannot be verified.

Resolution: `STALE_MARK_REST_FALLBACK_001` (ACTIVE) — adds a REST poll of `clob.polymarket.com/book?token_id=` whenever a mark is stale >30s. Once deployed and process restarted, ARI/NYM will get a fresh price and the sign criterion can be re-verified.

---

## Corrected blocker #2 — shadow-feed

Worker assessed this as FAIL. **Manager assessment: PASS.**

The criterion is: `confirm #shadow-feed not in tab-live HTML`. Inspection of `dashboard.html`:
- `#tab-live` closes at line 457 (`</section>`)
- `#shadow-feed` is at line 537, inside `#drawer > #tab-shadow`
- No occurrence of `shadow-feed` anywhere inside lines 410–457

Criterion is satisfied. `#shadow-feed` belongs to the Shadow Feed drawer panel, which is expected to remain in the HTML — it is architecturally separate from the LIVE tab.

---

## Scope / rollback

- No production code changed during this task (read-only).
- Nothing to roll back.
- PID 43288 still running.

---

## Next

Re-smoke after `STALE_MARK_REST_FALLBACK_001` is deployed and process restarted. Only the SSE sign criterion needs re-verification. All other criteria are already PASS and do not need to be re-run.

Brief: `TASK_DASHBOARD_REDESIGN_LIVE_SMOKE_003.json` — scope: SSE sign check only (reduced scope since all other criteria passed here).
