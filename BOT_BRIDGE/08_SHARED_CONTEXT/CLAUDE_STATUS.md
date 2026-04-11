# CLAUDE_STATUS.md — Manager Status Snapshot
## Last reconciled: 2026-04-11 — Tonight's trade audit APPROVED. Board reprioritized. Gate failure confirmed all-night. 5 fix tasks opened (2 ACTIVE, 4 QUEUED).

---

## ⚠ OPERATOR ACTION REQUIRED — BEFORE ANYTHING ELSE

**Delete `__pycache__/bot_core.cpython-*.pyc` and cold-restart the stack.**
Until this is done, confidence gate and cooldown checks are NOT running regardless of what code is patched.
See: `08_SHARED_CONTEXT/OPERATOR_ACTION_REQUIRED_001.md`

---

## System State

### Launcher
- `launch_all.py` — singleton guard active
- 4 children managed: `shadow_engine`, `bot_core`, `dashboard` (port 8900), `resolution_watcher`

### sports_bot_v2 (paper bot)
- Mode: LIVE TRADES ACTIVE (conservative mode, score=0.22)
- Bridge: ENABLED (`ENABLE_MODEL_BRIDGE = True`)
- **Confidence gate: NOT ENFORCING** — stale `__pycache__/bot_core.cpython-*.pyc` loading pre-patch bytecode since 18:41 CDT 2026-04-10. Patch in source (`bot_core.py` lines 504–525) but not executing.
- **Tonight's session: -$159.54 on 40 closed trades.** 31/42 (73.8%) sub-0.60 confidence. Gate failure was primary cause.
- **Currently open (all sub-0.60, all byproduct of broken gate):**
  - #254: conf=0.4438 BUY_NO mlb-wsh-mil entry=0.59295
  - #258: conf=0.3537 BUY_NO mlb-bos-stl entry=0.38190
  - #259: conf=0.3781 BUY_NO mlb-nyy-tb entry=0.9447 ← TP unreachable (fix queued)
- **Market cooldown: NOT SURVIVING RESTARTS** — in-memory only, wiped on every start
- **Ultra-low-price entry bug: CONFIRMED** — 7 trades at 0.05–0.07 stopped out in 1–2s (fix ACTIVE)
- **TP math bug: CONFIRMED** — entries >0.714 produce TP>1.0 (fix QUEUED)
- PnL math (SL/TP/fees/bankroll sizing): verified correct in tonight's audit

### Dashboard
- Running on port 8900
- Truth status: FIXED — realized PnL authoritative, mark_source chip correct, R25 sublabel correct
- At-bat upgrade: LIVE (DASHBOARD_LIVE_ATBAT_POLISH_001 PROVISIONAL PASS)
- Upstream trace: IN PROGRESS — MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001 ACTIVE

### mlb_model
- Authority: clean (execution_guard.py deleted, ROLLBACK_DISABLE removed)
- Producing today's recs via recommendation_api.py
- resolution_watcher running

---

## Completed This Reconciliation Pass

| Task | Outcome |
|------|---------|
| CONFIDENCE_HISTORY_AUDIT_001 | APPROVED — 0.60 floor realistic, bimodal distribution documented |
| CONFIDENCE_GATE_RUNTIME_VERIFY_001 | APPROVED — gate bypass confirmed |
| BRIDGE_ENTRY_GATE_WIRING_FIX_001 | APPROVED — patch in source; stale pyc preventing execution |
| DASHBOARD_LIVE_ATBAT_POLISH_001 | PROVISIONAL PASS |
| CONFIDENCE_GATE_POSTFIX_VERIFY_001 | PARTIAL PASS — gate fires at restart 1; stale pyc + dupe-slug bypasses found |
| DASHBOARD_MARK_SOURCE_AND_GUARD_MESSAGE_AUDIT_001 | PARTIAL PASS — dashboard layer cleared |
| TONIGHT_TRADE_AUDIT_2026_04_10 | **APPROVED** — 42-trade audit. Gate failure all-night. 5 new tasks opened. |

---

## Active Tasks

| Task | Priority | File Lock | Notes |
|------|----------|-----------|-------|
| MIN_ENTRY_PRICE_GATE_001 | CRITICAL | `core/risk.py` | Add min price gate (0.15 default) |
| MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001 | MEDIUM | read-only | Upstream trace, no file conflict |

## Queued Tasks (ordered)

| # | Task | Priority | Unblocked by |
|---|------|----------|-------------|
| 1 | TP_NEAR_RESOLUTION_CAP_FIX_001 | HIGH | MIN_ENTRY_PRICE_GATE_001 DONE |
| 2 | BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001 | HIGH | risk.py tasks DONE |
| 3 | MARKET_COOLDOWN_PERSIST_001 | HIGH | BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001 DONE |
| 4 | SESSION_PNL_TRUE_START_FIX_001 | MEDIUM | All critical tasks DONE |

---

## Open Items (not tasks)

| Item | Severity | Notes |
|------|----------|-------|
| **Pyc cache delete + cold restart** | CRITICAL OPERATOR ACTION | Must be done before any gate/cooldown fix takes effect |
| Trade #259 BUY_NO entry=0.9447 open | HIGH | TP unreachable; will exit via near_resolution or SL only |
| BUY_YES/BUY_NO sign semantics re-check | MEDIUM | Still real; deprioritized behind risk bugs per tonight's audit |
| next_three_up dashboard feature | LOW | Deferred — ESPN data unavailable |
| Polymarket user/fill stream | BLOCKED | Requires apiKey, secret, passphrase in .env |

---

## Blocked on Johnny (user action required)

| Item | What's needed |
|------|--------------|
| **Pyc cache clear** | `del __pycache__/bot_core.cpython-*.pyc` then cold restart via launch_all.py |
| **Gate verification after restart** | Confirm `BRIDGE GATE REJECT [check_entry_gates]` fires before any sub-0.60 entry |
| Polymarket user/fill stream | Add apiKey, secret, passphrase to .env |

---

## Confidence Gate Fix — Full Evidence Chain

| Step | Task | Status |
|------|------|--------|
| 1. Gate code written | MIN_ENTRY_CONFIDENCE_001 | APPROVED |
| 2. Gate confirmed un-wired | CONFIDENCE_GATE_RUNTIME_VERIFY_001 | APPROVED |
| 3. Wiring fix applied | BRIDGE_ENTRY_GATE_WIRING_FIX_001 | APPROVED — in source |
| 4. Post-fix verify | CONFIDENCE_GATE_POSTFIX_VERIFY_001 | PARTIAL PASS — pyc + dupe-slug bypasses found |
| 5. All-night audit confirms gate not firing | TONIGHT_TRADE_AUDIT_2026_04_10 | APPROVED — pyc confirmed as root cause |
| 6. Clear pyc + cold restart | OPERATOR_ACTION_REQUIRED_001 | **PENDING — operator must do this** |
| 7. Dupe-slug fix | BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001 | QUEUED |
| 8. Cooldown persistence | MARKET_COOLDOWN_PERSIST_001 | QUEUED |
