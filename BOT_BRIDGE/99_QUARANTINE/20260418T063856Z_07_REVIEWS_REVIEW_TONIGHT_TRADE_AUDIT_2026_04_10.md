# REVIEW — TONIGHT TRADE AUDIT 2026-04-10 (Evidence Record)
**Reviewer:** Claude (manager)
**Date:** 2026-04-11
**Verdict:** APPROVED — supersedes prior "runtime divergence" hypothesis

---

## Source

Direct live DB + log + code analysis performed during the 2026-04-10 session.
Trades audited: 42 (40 closed, 3 open as of audit time)

---

## Approved Findings (source-of-truth for task prioritization)

### F1 — Confidence gate did not fire all night [CRITICAL]
31 of 42 trades (73.8%) were below the 0.60 confidence floor.
Only 11 trades met the floor. All above-floor trades were profitable (+$43.09 combined).
All 29 below-floor closed trades lost a combined -$202.64.
Root cause: stale `__pycache__/bot_core.cpython-*.pyc` loading pre-patch bytecode on every restart after 18:41 CDT.

### F2 — CWS-KC market cooldown bypassed 8 entries [CRITICAL]
All 8 CWS-KC entries share market_id=1860423.
Gap-stop cooldowns (3600s) were set in the close path but never checked because `check_entry_gates()` — which hosts the cooldown check — was not being called.
After restart at 00:50:22 UTC, the in-memory cooldown dict was wiped, and the next entry (01:02:41 UTC) opened 93 seconds after a cooldown-setting gap_stop close.

### F3 — Instant stop-loss at extreme low entry prices [CRITICAL]
7 trades at 0.05–0.07 entry prices stopped out in 1–2 seconds.
At these prices, the bid-ask spread (~15–21%) already exceeds the 12% SL threshold at the moment of entry.
`check_entry_gates()` has a `spread_too_wide` check but it operates on absolute spread, not spread-relative-to-price.
No minimum entry price gate exists.

### F4 — TP math unreachable for near-1.0 entries [HIGH]
Trade #259: BUY_NO nyy-tb, entry_px=0.9447.
`get_tp_price = 0.9447 × 1.40 = 1.3226` — cannot be reached on a 0–1 contract.
TP condition will never fire. Max gain ≈ $2.93. SL loss ≈ $5.99 + fees.
`near_resolution_entry` gate (checks ask_no >= NEAR_RESOLUTION_PRICE) does not block this if NEAR_RESOLUTION_PRICE=0.97.

### F5 — Market cooldown is in-memory only [HIGH]
`_market_cooldown` dict is initialized empty on every process start.
Cooldown set after stop_loss/gap_stop close is wiped by any restart.
This is a persistent structural gap independent of the gate bug.

### F6 — PnL math verified correct [CLEARED]
stored_pnl = raw_pnl − fees: confirmed correct across all spot-checked trades.
SL trigger (entry × 0.88), TP trigger (entry × 1.40), gap_stop (−24%), trailing_stop: all verified correct.
Bankroll-aware sizing correctly shrinking with bankroll (3% × bankroll, $50 max).

### F7 — Session PnL visibility gap [MEDIUM]
state.json session_start_ts reflects last restart (00:50:22 UTC), not actual session start (~18:23 UTC).
Dashboard session PnL undercounts evening losses.

---

## Superseded Hypotheses

| Prior hypothesis | Status | Evidence that supersedes it |
|------------------|--------|----------------------------|
| "mark REST is a dashboard binding bug" | SUPERSEDED — mark REST is expected rest_fallback behavior (DASHBOARD_MARK_SOURCE_AND_GUARD_MESSAGE_AUDIT_001 PARTIAL PASS) | Dashboard layer cleared |
| "runtime divergence / cached state causing incorrect guard messages" | SUPERSEDED as primary issue — the real driver is gate not calling check_entry_gates() at all | Tonight's full trade audit shows gate failure is the root cause of all loss clustering |
| "bot is at 3/3 capacity, gate is entry-only" | STALE — bot has since taken 20+ more sub-floor entries; this was a snapshot, not a steady state | Tonight's 42-trade audit |

---

## Verdict

APPROVED as current strongest evidence.
All follow-on tasks should treat F1–F5 as confirmed root causes until a fix task supersedes them.
