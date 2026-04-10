# BANKROLL_ACCOUNTING_SPEC_001 — Bankroll & Session Accounting Rules
**Generated: 2026-04-10**
**Source files: dashboard_server.py, core/paper_exec.py, core/db.py (read-only)**
**Env values as of 2026-04-10**

---

## 1. Canonical Definitions — Verification Status

### lifetime_bankroll
- **Formula:** `STARTING_BANKROLL + SUM(pnl_usd WHERE status='closed')`
- **Source:** `core/db.py:total_realized_pnl()` → `SELECT COALESCE(SUM(pnl_usd),0) FROM trades WHERE status='closed'`
- **Used in:** `bot_core.py:_write_state()` → `state.json:pnl.realized`. Dashboard reads this via `_read_state()` → `net_pnl = state["pnl"]["realized"]` → `current = STARTING_BANKROLL + net_pnl`
- **Status:** ✓ VERIFIED — full lifetime history, no date cap, no fake resets
- **STARTING_BANKROLL:** `float(os.getenv("STARTING_BANKROLL", "500"))` — live value $500 (not set in .env, uses default)

### capital_committed
- **Formula:** `SUM(entry_px * qty WHERE status='open')`
- **Source:** `dashboard_server.py:_compute_open_trade_accounting()` → `SELECT side, entry_px, qty FROM trades WHERE status='open'`
- **Status:** ✓ VERIFIED — live DB query, no stale state, no closed trades included

### available_cash
- **Formula:** `max(0, lifetime_bankroll - capital_committed)`
- **Source:** `dashboard_server.py:_read_state()` line 520 (FIXED: now clamped to 0)
- **Status:** ✓ FIXED — previously could return negative; now clamped with WARNING log when overcommitted
- **Warning condition:** `log.warning("available_cash would be negative (committed=%.2f > bankroll=%.2f)")` in `_compute_open_trade_accounting()`

### live_equity
- **Formula:** `SUM(qty * current_price WHERE status='open')`
- **Price source:** `GLOBAL_STATE_HUB.snapshot()["current_price"]` — set from held token's best_bid (REST fallback) or WebSocket stream mark. asset_id = yes_token_id for BUY_YES, no_token_id for BUY_NO.
- **Status:** ✓ VERIFIED — held-side token used. No raw yes_price/no_price used in equity calculations.
- **Caveat:** When OB has no bids, REST path falls back to `best_ask` as current_price (thin book edge case — marginal overstatement). Not a systematic error.

### unrealized_pnl
- **Formula:** `SUM((current_price - entry_px) * qty WHERE status='open')`
- **Source:** `dashboard_server.py:_build_positions_mark()` — computed per position in positions loop
- **Status:** ✓ VERIFIED — separated from realized PnL, clearly labeled as `unrealized_pnl_usd`

### session_baseline
- **Definition:** `_session_start_ts = int(time.time())` set at `bot_core.py` module load (PID startup)
- **Status:** ✓ VERIFIED — in-memory global, not a DB write. Dashboard does not currently expose session_baseline as a dashboard field (shows lifetime bankroll only). `_session_loss_exceeded()` uses it for entry kill-switch logic.
- **Gap:** Dashboard /api/state does not expose session_baseline or session_pnl as explicit fields. Operator cannot see session-specific performance separately from lifetime. Low priority — not a correctness issue.

### session_pnl
- **Formula:** `SUM(pnl_usd WHERE ts_close >= _session_start_ts)` (used in `_session_loss_exceeded()`)
- **Status:** ✓ VERIFIED for loss-cap logic. Not exposed on dashboard — see session_baseline gap above.

---

## 2. Dashboard Numbers — Source Table

| Dashboard field | API path | Derivation | Status |
|----------------|----------|-----------|--------|
| `bankroll.start` | /api/state | `STARTING_BANKROLL` env var | ✓ |
| `bankroll.current` | /api/state | `STARTING_BANKROLL + state.pnl.realized` (lifetime DB query) | ✓ |
| `bankroll.net_pnl` | /api/state | `state.pnl.realized` from `total_realized_pnl()` | ✓ |
| `bankroll.capital_committed` | /api/state | `SUM(entry_px*qty WHERE open)` | ✓ |
| `bankroll.available_cash` | /api/state | `max(0, current - committed)` | ✓ FIXED |
| `live_equity_total` | /api/positions | `SUM(qty * current_price)` held-side | ✓ |
| `unrealized_pnl_usd` | /api/positions | `(current_price - entry_px) * qty` per trade | ✓ |
| `/api/bankroll net_pnl` | /api/bankroll | `SUM(pnl_usd WHERE closed)` lifetime | ✓ FIXED |
| `/api/bankroll history` | /api/bankroll | Daily PnL by day, last 30 days | ✓ (display only) |
| `r25.win_rate` | /api/state | Last 25 closed trades WIN count / 25 | ✓ |

---

## 3. Invariants — Verification Status

| Rule | Status | Evidence |
|------|--------|----------|
| NO_DOUBLE_COUNTING | ✓ CONFIRMED | Open trades: `WHERE status='open'`. Closed PnL: `WHERE status='closed'`. Never mixed in same computation. |
| AVAILABLE_CASH_NEVER_NEGATIVE | ✓ FIXED | `_compute_open_trade_accounting()` now clamps to `max(0, ...)` + logs WARNING. `_read_state()` clamps too. |
| LIVE_EQUITY_USES_HELD_SIDE_PRICE | ✓ CONFIRMED | asset_id = held token (BUY_YES→yes_token, BUY_NO→no_token). current_price = best_bid of held token. No raw yes/no prices in equity math. |
| SESSION_BASELINE_IS_SNAPSHOT | ✓ CONFIRMED | `_session_start_ts = int(time.time())` — module-level global, in-memory only. No DB write. |
| INITIAL_BANKROLL_IS_CONFIGURABLE | ✓ CONFIRMED | `STARTING_BANKROLL = float(os.getenv("STARTING_BANKROLL", "500"))` |

---

## 4. Gaps Fixed in This Phase

### FIX-1: available_cash clamped to non-negative
- **Where:** `dashboard_server.py:_compute_open_trade_accounting()` and `_read_state()`
- **Before:** `available_cash = STARTING_BANKROLL - committed` (could be negative)
- **After:** `available_cash = max(0.0, STARTING_BANKROLL - committed)` + WARNING log

### FIX-2: /api/bankroll uses lifetime PnL query, not 30-day sum
- **Where:** `dashboard_server.py:/api/bankroll` handler
- **Before:** `net = sum(d["pnl"] for d in _daily_pnl_history())` — LIMIT 30 days, would miss history beyond 30 trading days
- **After:** Direct `SELECT COALESCE(SUM(pnl_usd),0) FROM trades WHERE status='closed'` — full lifetime. Daily history still returned for chart display.

---

## 5. Remaining Gaps

| Gap | Severity | Notes |
|-----|----------|-------|
| Session PnL not displayed on dashboard | LOW | `_session_start_ts` exists, session_pnl computable, but not surfaced in /api/state bankroll block. Operator must compute manually. |
| Session total USD commitment cap | HIGH | Carried from POSITION_SIZING_RULES_001 — `MAX_TOTAL_COMMITTED_USD` env cap not implemented. Max exposure = 3 × $100 = $300. |
| live_equity asks-as-fallback | LOW | When OB has no bids, REST path uses best_ask. Thin book edge case only, not systematic. |
