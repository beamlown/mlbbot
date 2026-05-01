# REVIEW_BANKROLL_SESSION_RULES_001

**Decision: APPROVED**
**Reviewed: 2026-04-10**

---

## Scope check

- Allowed files: `dashboard_server.py`, `core/paper_exec.py`. Only `dashboard_server.py` modified. ✓
- `core/paper_exec.py` read and confirmed correct — no changes needed. ✓
- `git diff --name-only` shows `sports_bot_v2/dashboard_server.py` (and `bot_core.py` from prior task). ✓
- `bot_core.py` not touched in this task. ✓
- No TP/SL thresholds, no strategy logic changed. ✓

---

## Invariant evaluation

| Rule | Verdict | Evidence |
|------|---------|----------|
| NO_DOUBLE_COUNTING | ✓ CONFIRMED | Open: `WHERE status='open'`. Closed: `WHERE status='closed'`. Never combined in same PnL sum. |
| AVAILABLE_CASH_NEVER_NEGATIVE | ✓ FIXED | `_compute_open_trade_accounting()` now: `raw_cash = STARTING_BANKROLL - committed; if raw_cash < 0: log.warning(...); return max(0.0, raw_cash)`. `_read_state()` also clamps: `max(0.0, current - committed)`. |
| LIVE_EQUITY_USES_HELD_SIDE_PRICE | ✓ CONFIRMED | `asset_id = yes_token_id if BUY_YES else no_token_id`. `current_price = best_bid` of that token. No raw `yes_price`/`no_price` in equity math confirmed by grep. |
| SESSION_BASELINE_IS_SNAPSHOT | ✓ CONFIRMED | `_session_start_ts = int(time.time())` in `bot_core.py` module scope — in-memory only, no DB write. |
| INITIAL_BANKROLL_IS_CONFIGURABLE | ✓ CONFIRMED | `STARTING_BANKROLL = float(os.getenv("STARTING_BANKROLL", "500"))` — live value $500 (env default, not set in .env). |

---

## Bugs fixed

### 1. available_cash clamped to 0 (AVAILABLE_CASH_NEVER_NEGATIVE)
- **Before:** `round(STARTING_BANKROLL - committed, 2)` — could be negative if committed > bankroll
- **After:** `round(max(0.0, raw_cash), 2)` with `log.warning(...)` when overcommitted
- **Locations:** `_compute_open_trade_accounting()` and `_read_state()`

### 2. /api/bankroll lifetime PnL (audit gap: MED severity)
- **Before:** `net = sum(d["pnl"] for d in _daily_pnl_history())` — LIMIT 30 daily rows, would drop history beyond 30 trading days
- **After:** Direct SQL `SELECT COALESCE(SUM(pnl_usd),0) FROM trades WHERE status='closed'` with fallback to daily sum on error. Daily history still returned for chart.

---

## Acceptance criteria

- [x] All 5 accounting invariants confirmed or fixed
- [x] `BANKROLL_ACCOUNTING_SPEC_001.md` written and complete
- [x] available_cash formula matches canonical definition (clamp to 0)
- [x] live_equity uses held-side bid price only
- [x] No fake session resets — confirmed in-memory only
- [x] `python -m py_compile dashboard_server.py` — PASS
- [x] `python -m py_compile core/paper_exec.py` — PASS
- [x] Only allowed_files changed

---

## Rollback

3 localized hunks in `dashboard_server.py` — all additive (clamp + WARNING, SQL fallback query). Easily reversible. No schema changes, no DB writes.
