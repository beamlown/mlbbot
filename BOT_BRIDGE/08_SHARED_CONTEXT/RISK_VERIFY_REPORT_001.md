# RISK_VERIFY_REPORT_001 — End-to-End Risk System Verification
**Generated: 2026-04-10**
**Phases verified: TP_SL_SCHEMA_NORMALIZATION_001, POSITION_SIZING_RULES_001, EXECUTION_RISK_MONITOR_001, BANKROLL_SESSION_RULES_001**
**Overall verdict: SYSTEM VERIFIED**

---

## Verification Results Table

| Check | Result | Evidence | File:Line |
|-------|--------|---------|-----------|
| TP_SL_CANONICAL_FUNCTIONS | ✓ PASS | `get_tp_price()`, `get_sl_price()` exist; called by `check_exit()` | `risk.py:57-64`, `risk.py:240-241` |
| TP_SL_THRESHOLDS_MATCH_ENV | ✓ PASS | .env values match spec exactly (see §1) | `.env:45-49` |
| EXIT_REASONS_COMPLETE | ✓ PASS | 6 exit reasons all logged + DB persisted (see §2) | `risk.py:246-273`, `bot_core.py:693+` |
| SIZING_FORMULA_MATCHES_SPEC | ✓ PASS | Code matches SIZING_RULES_SPEC_001.md exactly | `paper_exec.py:27-40,81` |
| SIZING_CAPS_ACTIVE | ✓ PASS | MAX_POSITION_SIZE_USD=$100 on both paths; MAX_CONCURRENT_TRADES=3 in entry gates | `paper_exec.py:40,76`, `risk.py:201` |
| HELD_SIDE_PRICE_ONLY | ✓ PASS | bid_yes/bid_no only in: format strings (log), `_fill_price_exit()` (correct held-side), `_held_bid()` accessor — never cross-side in equity/PnL | `paper_exec.py:54,56`, `risk.py:184,186` |
| NONE_OB_HANDLING | ✓ PASS | `WARNING "Exit check skipped ... reason=empty_ob"` + stale OB warning after STALE_OB_WARN_SECONDS | `bot_core.py:661,670` |
| BANKROLL_NUMBERS_MATCH_DB | ✓ PASS | DB SUM(pnl_usd WHERE closed) = $351.9051; state.json pnl.realized = $351.9051 — exact match | DB query, `runtime/state.json` |
| AVAILABLE_CASH_FORMULA | ✓ PASS | `max(0, current - committed)` in both `_compute_open_trade_accounting()` and `_read_state()` | `dashboard_server.py:319,520` |
| LIVE_EQUITY_SOURCE | ✓ PASS | asset_id = held token (BUY_YES→yes_token, BUY_NO→no_token); current_price = best_bid of held token | `dashboard_server.py:359,403` |
| RESOLVED_MARKET_CLOSE | ✓ PASS | Force-close path present; logs `"CLOSE trade=%d ... reason=market_resolved exit_px=%.4f pnl=%.4f"` | `bot_core.py:633-640` |
| COOLDOWNS_CORRECT | ✓ PASS | near_resolution=+600s, stop_loss=+1800s, gap_stop=+3600s. No cooldown on take_profit, trailing_stop, time_exit, market_resolved | `bot_core.py:695,698,701` |

---

## §1 — TP/SL Threshold Verification

| Parameter | .env value | Code default | Live value (env override) |
|-----------|-----------|--------------|--------------------------|
| AUTO_TAKE_PROFIT_PCT | 0.40 | 0.85 | **0.40** ✓ |
| AUTO_STOP_LOSS_PCT | 0.12 | 0.20 | **0.12** ✓ |
| NEAR_RESOLUTION_PRICE | 0.97 | 0.92 | **0.97** ✓ |
| TRAILING_STOP_ACTIVATE_PCT | 0.10 | 0.15 | **0.10** ✓ |
| TRAILING_STOP_DRAWDOWN_PCT | 0.12 | 0.20 | **0.12** ✓ |

Note: Code defaults differ from .env values — but .env is loaded at startup, so live runtime uses .env values. No risk unless bot starts without .env present.

---

## §2 — Exit Reasons Completeness

| Exit reason | check_exit() line | bot_core.py log | DB persisted via |
|-------------|------------------|-----------------|-----------------|
| gap_stop | risk.py:246 | CLOSE logger.info:693 | close_position() → close_trade() |
| near_resolution | risk.py:250 | CLOSE logger.info:693 | close_position() → close_trade() |
| take_profit | risk.py:254 | CLOSE logger.info:693 | close_position() → close_trade() |
| trailing_stop | risk.py:265 | CLOSE logger.info:693 | close_position() → close_trade() |
| stop_loss | risk.py:270 | CLOSE logger.info:693 | close_position() → close_trade() |
| time_exit | risk.py:273 | CLOSE logger.info:693 | close_position() → close_trade() |
| market_resolved | (bot_core force-close) | CLOSE logger.info:634 | close_trade() directly |

All 7 exit paths log at INFO and persist to DB. ✓

---

## §3 — Bankroll Accounting Snapshot

| Metric | Value | Source |
|--------|-------|--------|
| STARTING_BANKROLL | $500.00 | env var (default) |
| Realized PnL (lifetime) | $351.9051 | DB + state.json (exact match) |
| Lifetime bankroll | $851.91 | STARTING_BANKROLL + realized |
| Capital committed | $50.00 | 1 open trade: entry_px * qty |
| Available cash | $801.91 | lifetime_bankroll - committed |
| Open trades | 1 | DB |
| Unrealized PnL | $2.3312 | state.json (mark-to-market) |

---

## §4 — Remaining Gaps (Carry-Forward)

| Gap | Severity | Deferred to |
|-----|----------|-------------|
| No per-session total USD commitment cap (MAX_TOTAL_COMMITTED_USD) | HIGH | RISK_AND_TP_AUDIT_001 (document) |
| Bankroll-aware sizing (size scales with bankroll drawdown) | HIGH | Future implementation |
| Code defaults in risk.py don't match .env live values | LOW | Risk only if bot starts without .env; acceptable given .env is required |
| Session PnL not displayed on dashboard | LOW | Future feature |
| live_equity uses ask as fallback on empty bid (thin books) | LOW | Acceptable edge case |

---

## Overall Verdict: SYSTEM VERIFIED

All 12 verification checks PASS. The risk system, sizing, held-side pricing, close logic, and bankroll accounting are operating correctly as a system. Two HIGH-severity gaps (session USD cap, bankroll-aware sizing) are documented and deferred — they are design gaps, not broken invariants. The system is ready for phase 6 (final audit document).
