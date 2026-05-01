# REVIEW_RISK_AND_TP_VERIFY_001

**Decision: APPROVED**
**Reviewed: 2026-04-10**

---

## Scope check

- Task is read-only. No production files modified. ✓
- `git diff` confirms only `bot_core.py` and `dashboard_server.py` from prior tasks — nothing new. ✓
- `RISK_VERIFY_REPORT_001.md` written to `08_SHARED_CONTEXT/`. ✓

---

## Checks passed: 12/12

| Check | Result |
|-------|--------|
| TP_SL_CANONICAL_FUNCTIONS | ✓ PASS — `get_tp_price()`, `get_sl_price()` are the sole source of TP/SL prices |
| TP_SL_THRESHOLDS_MATCH_ENV | ✓ PASS — all 5 .env values confirmed (0.40, 0.12, 0.97, 0.10, 0.12) |
| EXIT_REASONS_COMPLETE | ✓ PASS — 7 exit paths all log INFO and persist to DB |
| SIZING_FORMULA_MATCHES_SPEC | ✓ PASS — code matches SIZING_RULES_SPEC_001.md exactly |
| SIZING_CAPS_ACTIVE | ✓ PASS — $100 per-trade cap on both paths, count cap at MAX_CONCURRENT_TRADES=3 |
| HELD_SIDE_PRICE_ONLY | ✓ PASS — zero cross-side bid usage in equity/PnL math |
| NONE_OB_HANDLING | ✓ PASS — WARNING logged on empty OB; STALE OB warning after 300s |
| BANKROLL_NUMBERS_MATCH_DB | ✓ PASS — DB: $351.9051 = state.json: $351.9051 (exact) |
| AVAILABLE_CASH_FORMULA | ✓ PASS — `max(0, lifetime_bankroll - committed)` confirmed |
| LIVE_EQUITY_SOURCE | ✓ PASS — held token bid_yes/bid_no used as current_price |
| RESOLVED_MARKET_CLOSE | ✓ PASS — force-close path confirmed with INFO log and reason=market_resolved |
| COOLDOWNS_CORRECT | ✓ PASS — exactly 3 assignments at correct durations |

---

## Acceptance criteria

- [x] All 12 checks produce PASS
- [x] Zero FAILs without explanation
- [x] DB PnL = dashboard PnL within $0.01 (exact match: $351.9051)
- [x] No raw bid_yes/bid_no in equity/PnL calculations
- [x] RISK_VERIFY_REPORT_001.md written with complete evidence table
- [x] No production file modified

---

## Phase 6 gate

**phase_6_ready: true** — RISK_AND_TP_AUDIT_001 may be promoted to ACTIVE.

Remaining HIGH gaps (session USD cap, bankroll-aware sizing) are design gaps, not broken invariants. System is operating correctly within its current design constraints.
