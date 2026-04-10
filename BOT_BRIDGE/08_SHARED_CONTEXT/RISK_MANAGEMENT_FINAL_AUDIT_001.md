# RISK_MANAGEMENT_FINAL_AUDIT_001
**Risk Management System — Final Audit Document**
**Date: 2026-04-10**
**Covers phases: RISK_PIPELINE_AUDIT_001 through RISK_AND_TP_VERIFY_001**
**Overall verdict: SYSTEM VERIFIED**

---

## 1. SYSTEM OVERVIEW

The `sports_bot_v2` risk system is a multi-layer stack that governs when the bot enters a position, how large that position is, when it exits, and how those events are accounted for financially. Entries are gated by a waterfall of guards in `core/risk.py` (spread, depth, confidence, concurrency, market validity, cooldowns) and a session/daily loss kill-switch in `bot_core.py`. Once open, positions are monitored each loop by `check_exit()` in `core/risk.py`, which fires on six conditions: gap stop, near-resolution, take-profit, trailing stop, stop-loss, and time exit. A seventh path — `market_resolved` — force-closes positions when the Polymarket resolution watcher confirms settlement, bypassing the orderbook entirely. Position size is determined by a tiered confidence formula bounded by a per-trade dollar cap; all arithmetic uses the held-side contract price (bid of the held YES or NO token), never a cross-side price. Realized PnL is accumulated in a SQLite database without modification; the dashboard derives all financial metrics from this single source of truth.

---

## 2. FILE MAP

| File | Role in Risk System | Phases That Modified It | State |
|------|--------------------|-----------------------|-------|
| `core/risk.py` | Entry gate waterfall, TP/SL canonical functions, check_exit(), _held_bid() | TP_SL_SCHEMA_NORMALIZATION_001 | ✓ VERIFIED |
| `core/paper_exec.py` | Position sizing, fill price, open_position(), close_position() | TP_SL_SCHEMA_NORMALIZATION_001 | ✓ VERIFIED |
| `bot_core.py` | Main loop, entry/exit orchestration, session loss caps, resolution watcher integration, exit loop hardening | SL_COOLDOWN_001, BOT_DATE_GATE_DEFENSE_001, RESOLUTION_WATCHER_INTEGRATE_001, EXIT_GAME_AWARE_002, MARKET_RESOLVED_DB_FIELDS_001, SESSION_LOSS_CAP_001, EXECUTION_RISK_MONITOR_001 | ✓ VERIFIED |
| `dashboard_server.py` | Bankroll accounting, /api/state, /api/bankroll, live equity | BANKROLL_SESSION_RULES_001 | ✓ VERIFIED |
| `core/db.py` | DB schema, trade persistence, total_realized_pnl() | (read-only in this pack) | ✓ UNCHANGED |
| `integration/resolution_watcher.py` | Polls Gamma API, writes runtime/resolved_markets.json | RESOLUTION_WATCHER_BUILD_001 | ✓ VERIFIED |
| `.env` | All configurable thresholds and caps | EXIT_PARAMS_TIGHTEN_001 | ✓ VERIFIED |
| `core/types.py` | Trade, Signal, Market, OBSnapshot dataclasses | TP_SL_SCHEMA_NORMALIZATION_001 | ✓ VERIFIED |

---

## 3. TP/SL ARCHITECTURE

### Canonical Functions (risk.py:57-64)
```python
def get_tp_price(trade: Trade) -> float:
    return (trade.entry_px or 0.0) * (1.0 + AUTO_TAKE_PROFIT_PCT)

def get_sl_price(trade: Trade) -> float:
    return (trade.entry_px or 0.0) * (1.0 - AUTO_STOP_LOSS_PCT)
```
These are the **sole** source of TP and SL prices. All callers use these functions.

### Live Threshold Values

| Parameter | Env Var | .env Value | Code Default |
|-----------|---------|-----------|--------------|
| Take-profit threshold | AUTO_TAKE_PROFIT_PCT | **0.40** | 0.85 |
| Stop-loss threshold | AUTO_STOP_LOSS_PCT | **0.12** | 0.20 |
| Near-resolution gate | NEAR_RESOLUTION_PRICE | **0.97** | 0.92 |
| Trailing stop activate | TRAILING_STOP_ACTIVATE_PCT | **0.10** | 0.15 |
| Trailing stop drawdown | TRAILING_STOP_DRAWDOWN_PCT | **0.12** | 0.20 |
| Gap stop multiplier | (2 × AUTO_STOP_LOSS_PCT) | **0.24** | computed |

*Note: Code defaults differ from .env live values. The .env file is required for correct operation.*

### Exit Reason Taxonomy

| Reason | Trigger | Cooldown | Source |
|--------|---------|---------|--------|
| `gap_stop` | held_unrealized_pct < -0.24 | 3600s | risk.py:244-246 |
| `near_resolution` | current_held_price ≥ 0.97 | 600s | risk.py:248-250 |
| `take_profit` | current_held_price ≥ entry * 1.40 | none | risk.py:252-254 |
| `trailing_stop` | drawdown from peak ≥ 0.12 (after +10% peak) | none | risk.py:261-265 |
| `stop_loss` | current_held_price ≤ entry * 0.88 | 1800s | risk.py:267-270 |
| `time_exit` | time_to_end < TIME_EXIT_BUFFER_SECONDS (300s) | none | risk.py:272-273 |
| `market_resolved` | Polymarket settlement confirmed by resolution watcher | none | bot_core.py:614-641 |

---

## 4. POSITION SIZING

### Formula (paper_exec.py:27-40,81)
```
If signal.components["recommended_size_dollars"] is set:
    size_usd = clamp(recommended_size_dollars, 0, MAX_POSITION_SIZE_USD)
Else:
    tier_mult = confidence_tier_multiplier(confidence)
    size_usd = clamp(PAPER_POSITION_SIZE_USD * tier_mult, 0, MAX_POSITION_SIZE_USD)

qty = size_usd / fill_px
```

### Confidence Tier Table

| Confidence Range | Tier | Multiplier | Size (base=$50) |
|-----------------|------|-----------|----------------|
| conf < 0.70 | Base | 1.00× | $50.00 |
| 0.70 ≤ conf < 0.80 | High | 1.25× | $62.50 |
| conf ≥ 0.80 | Very High | 1.50× | $75.00 |
| Any (cap) | — | — | max $100.00 |

### All Caps

| Cap | Env Var | Live Value | Enforcement |
|-----|---------|-----------|-------------|
| Per-trade max | MAX_POSITION_SIZE_USD | $100 | paper_exec.py:40,76 |
| Concurrent trades (count) | MAX_CONCURRENT_TRADES | 3 | risk.py:201 |
| Per-market concurrent | MAX_TRADES_PER_MARKET | 1 | risk.py:205 |
| Liquidity gate | MIN_TOUCH_DEPTH_USD | $200 | risk.py:188-190 |
| Per-session USD total | (missing) | — | GAP — see §9 |

### Worked Example
**Given:** confidence=0.65, bankroll=$900, 1 open position, depth=$200
- Depth gate: $200 ≥ MIN_TOUCH_DEPTH_USD=$200 ✓ (passes exactly)
- Concurrent gate: 1 < 3 ✓
- tier_mult = 1.0 (conf < 0.70)
- size_usd = $50.00 × 1.0 = $50.00 (below $100 cap)
- fill_px = ask_yes × 1.005; assume ask=0.50 → fill=0.5025
- qty = $50.00 / 0.5025 = 99.50 contracts
- **Bankroll ($900) not factored — documented gap**

---

## 5. HELD-SIDE PRICING CHAIN

```
Polymarket CLOB (WebSocket or REST)
    ↓
  bid_yes / bid_no (for the held token)
    ↓
  _held_bid(side, ob) in risk.py:47-48
    → returns ob.bid_yes if BUY_YES else ob.bid_no
    → returns None on empty OB (triggers WARNING in bot_core.py:661)
    ↓
  check_exit() in risk.py:235
    → held_unrealized_pct = (current_held_price - entry_px) / entry_px
    → compared against TP/SL thresholds
    ↓
  close_position() in paper_exec.py:138
    → exit price = _fill_price_exit(side, ob) = bid_side × (1 - SLIPPAGE)
    → PnL = (exit_px - entry_px) × qty
    ↓
  close_trade() in core/db.py
    → persists exit_px, pnl_usd, reason_close, ts_close
```

**No raw YES/NO price crosses this chain.** All bid/ask accesses are held-side only. Verified by grep across all 4 production files (RISK_VERIFY_REPORT_001.md §check HELD_SIDE_PRICE_ONLY).

---

## 6. BANKROLL AND SESSION ACCOUNTING

### Verified Computation Paths

| Metric | Formula | Source |
|--------|---------|--------|
| lifetime_bankroll | STARTING_BANKROLL + SUM(pnl_usd WHERE closed) | db.py:total_realized_pnl() — no date cap |
| capital_committed | SUM(entry_px × qty WHERE open) | dashboard_server.py:_compute_open_trade_accounting() |
| available_cash | max(0, lifetime_bankroll − committed) | dashboard_server.py:519-520 (clamped after BANKROLL fix) |
| live_equity | SUM(qty × current_held_price WHERE open) | dashboard_server.py:_build_positions_mark():469 |
| unrealized_pnl | SUM((current_price − entry_px) × qty WHERE open) | dashboard_server.py:470 |
| /api/bankroll net_pnl | SELECT SUM(pnl_usd) WHERE closed (full lifetime) | Fixed from 30-day cap in BANKROLL_SESSION_RULES_001 |

### Live Snapshot (2026-04-10)
- Realized PnL: **$351.91** (172 closed trades)
- Lifetime bankroll: **$851.91**
- Capital committed: **$50.00** (1 open trade)
- Available cash: **$801.91**
- DB ↔ dashboard: **exact match verified**

---

## 7. CLOSE LOGIC AND RESOLUTION

### Standard Close Flow
1. `check_exit()` evaluates held-side bid against TP/SL/gap/trailing/near_resolution/time thresholds
2. If `should_close=True` and reason ≠ `near_resolution` (or watcher empty/unconfirmed): `close_position()` computes exit_px and PnL
3. `close_trade()` persists all 5 required fields: exit_px, pnl_usd, fees_usd, reason_close, ts_close
4. Cooldown set if applicable

### Hold-to-Resolution Gate (EXIT_GAME_AWARE_002)
If `near_resolution` fires AND the resolution watcher is running AND the market is not yet in `resolved_markets.json` → **hold** (suppress close, await confirmation). Safe degradation: if watcher dict is empty (not running), falls through to normal near_resolution close.

### Market Resolved Force-Close (RESOLUTION_WATCHER_INTEGRATE_001)
- Fires **before** check_exit() on each open trade
- Reads `runtime/resolved_markets.json` (written by `integration/resolution_watcher.py`)
- Closes at `yes_resolution_price` (BUY_YES) or `no_resolution_price` (BUY_NO)
- Sets `reason_close='market_resolved'`, `ts_close=int(time.time())`
- No cooldown, no OB required

### Cooldown Table
| Trigger | Cooldown | Effect |
|---------|---------|--------|
| near_resolution exit | 600s | No re-entry for 10 minutes |
| stop_loss exit | 1800s | No re-entry for 30 minutes |
| gap_stop exit | 3600s | No re-entry for 60 minutes |
| take_profit, trailing_stop, time_exit, market_resolved | none | Immediate re-entry eligible |

---

## 8. VERIFICATION RESULTS

| Check | Result | Key Evidence |
|-------|--------|-------------|
| TP_SL_CANONICAL_FUNCTIONS | ✓ PASS | get_tp_price/get_sl_price sole source |
| TP_SL_THRESHOLDS_MATCH_ENV | ✓ PASS | .env:45-49 all 5 values confirmed |
| EXIT_REASONS_COMPLETE | ✓ PASS | 7 exit paths all log + persist |
| SIZING_FORMULA_MATCHES_SPEC | ✓ PASS | paper_exec.py:27-40 matches spec |
| SIZING_CAPS_ACTIVE | ✓ PASS | $100 cap, count cap both confirmed |
| HELD_SIDE_PRICE_ONLY | ✓ PASS | Zero cross-side usage in equity math |
| NONE_OB_HANDLING | ✓ PASS | WARNING logged on empty OB |
| BANKROLL_NUMBERS_MATCH_DB | ✓ PASS | $351.9051 exact match |
| AVAILABLE_CASH_FORMULA | ✓ PASS | max(0, lifetime − committed) |
| LIVE_EQUITY_SOURCE | ✓ PASS | Held token bid_yes/bid_no |
| RESOLVED_MARKET_CLOSE | ✓ PASS | Force-close path confirmed |
| COOLDOWNS_CORRECT | ✓ PASS | Exactly 3 assignments, correct durations |

**Overall: 12/12 PASS — SYSTEM VERIFIED**

---

## 9. GAPS AND REMAINING RISKS

| Gap ID | Description | Severity | Status | Recommended Action |
|--------|-------------|---------|--------|-------------------|
| GAP-SIZE-SESSION | No per-session total USD commitment cap. Max exposure = 3 × $100 = $300 with no dollar ceiling. | HIGH | OPEN | Add MAX_TOTAL_COMMITTED_USD env var; enforce in check_entry_gates() or bot_core.py entry section |
| GAP-SIZE-BANKROLL | Position sizing ignores bankroll balance. $50 base regardless of drawdown. | HIGH | OPEN | Add bankroll-fraction sizing: size_usd = max(MIN_SIZE, bankroll × RISK_PCT_PER_TRADE) |
| GAP-DEFAULTS | Code defaults in risk.py differ from .env live values (e.g. TP 0.85 vs live 0.40). Startup without .env would trade with wrong thresholds. | LOW | OPEN | Either align defaults to live values or add startup assertion that .env loaded correctly |
| GAP-SESSION-DASHBOARD | Session PnL (since PID start) not displayed on dashboard. Only lifetime shown. | LOW | OPEN | Add session_pnl to /api/state bankroll block; requires passing _session_start_ts to dashboard or separate endpoint |
| GAP-EQUITY-ASK-FALLBACK | When OB has no bids, REST fallback uses best_ask as current_price. Overstates live_equity in thin markets. | LOW | OPEN | Use None or "stale" flag instead of ask when no bids available |
| GAP-STALE-OB-FORCED-EXIT | Stale OB warning implemented but forced exit not. Trade stuck open with empty OB after 300s only generates a log warning. | LOW | PARTIAL | Implement forced time-based stop on STALE_OB_WARN_SECONDS + configurable extension |

---

## 10. RECOMMENDED NEXT ACTIONS

Priority ordered. Each item is bounded and implementable without strategy redesign.

1. **Add MAX_TOTAL_COMMITTED_USD cap** (HIGH)
   - *What:* Env var gating total `SUM(entry_px × qty)` across open trades. Block new entries if sum would exceed cap.
   - *Why:* Current count cap (3 trades) allows up to $300 committed in paper mode. If PAPER_POSITION_SIZE_USD is raised, exposure grows unbounded.
   - *Files:* `bot_core.py` or `core/risk.py:check_entry_gates()`
   - *Impact:* Closes the largest remaining risk gap. Zero strategy change.

2. **Bankroll-aware base sizing** (HIGH)
   - *What:* Replace fixed `PAPER_POSITION_SIZE_USD` with `bankroll × RISK_PCT_PER_TRADE` (e.g. 5% of current bankroll). Add env vars RISK_PCT_PER_TRADE, MIN_POSITION_USD.
   - *Why:* After a drawdown, the bot sizes identically to peak — amplifying loss rate during bad runs.
   - *Files:* `core/paper_exec.py`
   - *Impact:* Makes sizing self-regulating with bankroll health.

3. **Align risk.py code defaults to live values** (LOW)
   - *What:* Change hardcoded defaults in risk.py to match .env values (TP=0.40, SL=0.12, NRP=0.97, TSA=0.10, TSD=0.12). Add startup log confirming thresholds at launch.
   - *Why:* Startup without .env would run with wrong thresholds silently.
   - *Files:* `core/risk.py`
   - *Impact:* Fail-safe improvement, no behavior change with .env present.

4. **Session PnL on dashboard** (LOW)
   - *What:* Add `session_pnl` and `session_baseline` to `/api/state` bankroll block. Compute as `SUM(pnl_usd WHERE ts_close >= session_start_ts)`.
   - *Why:* Operator cannot distinguish today's performance from lifetime history at a glance.
   - *Files:* `dashboard_server.py` — needs session_start_ts passed via state.json or a separate API call to bot process
   - *Impact:* Operational visibility improvement.

5. **Forced exit on prolonged stale OB** (LOW)
   - *What:* If `_held_bid()` is None and trade has been open > STALE_OB_MAX_SECONDS (configurable), force close at last-known bid or market_resolved price.
   - *Why:* Current implementation warns but doesn't act — trade can stay stuck indefinitely if OB never recovers and market isn't resolved.
   - *Files:* `bot_core.py`
   - *Impact:* Prevents indefinitely open positions on thin/dead markets.
