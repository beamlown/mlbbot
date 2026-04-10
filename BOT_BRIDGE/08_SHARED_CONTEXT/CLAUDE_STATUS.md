# CLAUDE_STATUS.md — Manager Status Snapshot
## Last reconciled: 2026-04-10 — Post gate-wiring fix. Confidence gate bug confirmed and patched. Postfix verify pending.

---

## System State

### Launcher
- `launch_all.py` — singleton guard active
- 4 children managed: `shadow_engine`, `bot_core`, `dashboard` (port 8900), `resolution_watcher`

### sports_bot_v2 (paper bot)
- Mode: **LIVE TRADES ACTIVE**
- Bridge: ENABLED (`ENABLE_MODEL_BRIDGE = True`)
- **PnL: +$405.89 realized** (last verified at DASHBOARD_TRUTH_FIXES_001; will shift as live trades settle)
- Authority model: BRIDGE-ONLY (local origination removed by AUTHORITY_SEPARATION_CLEANUP_001)
- **Confidence gate: PATCHED but requires restart** — `check_entry_gates()` now wired into bridge path in `bot_core.py` (BRIDGE_ENTRY_GATE_WIRING_FIX_001 APPROVED). Gate was previously bypassed by all bridge entries. **Restart required to activate patch.**
- Currently open below-floor trades: trade 223 (conf=0.3353), trade 224 (conf=0.3996) — entered pre-fix, will run to existing exit conditions. Not at risk from the new gate (entry-only, not exit-only).

### Dashboard
- Running on port 8900
- At-bat upgrade live: dominant score hierarchy, count chips, batter/pitcher identity, last-play text (DASHBOARD_LIVE_ATBAT_POLISH_001 PROVISIONAL PASS)
- **Note:** dashboard_server.py was modified by ATBAT task — if not in Flask debug mode, dashboard_server.py process restart needed for current_batter/pitcher fields to appear
- **Truth status: FIXED** — Realized P&L authoritative, mark_source chip visible, R25 sublabel correct

### mlb_model
- Authority: clean (execution_guard.py deleted, ROLLBACK_DISABLE removed)
- Producing today's recs via recommendation_api.py
- resolution_watcher running — marking resolved=True on settled markets

---

## Completed This Reconciliation Pass

| Task | Outcome |
|------|---------|
| CONFIDENCE_HISTORY_AUDIT_001 | APPROVED — 0.60 floor is realistic; 69% trade frequency reduction expected; bimodal model structure documented |
| CONFIDENCE_GATE_RUNTIME_VERIFY_001 | APPROVED — real bug confirmed; bridge path bypassed check_entry_gates(); trades 223/224 confirmed post-restart |
| BRIDGE_ENTRY_GATE_WIRING_FIX_001 | APPROVED — patch applied to bot_core.py; py_compile PASS; restart required |
| DASHBOARD_LIVE_ATBAT_POLISH_001 | PROVISIONAL PASS — at-bat UI upgraded; next_three_up deferred (data unavailable in ESPN path) |

---

## Open Items (not tasks — operator awareness only)

| Item | Severity | Notes |
|------|----------|-------|
| **Bot restart required** | HIGH | BRIDGE_ENTRY_GATE_WIRING_FIX_001 patch requires bot_core.py process restart. Until restart, bridge entries bypass confidence gate. |
| **Postfix gate verify pending** | HIGH | CONFIDENCE_GATE_POSTFIX_VERIFY_001 ACTIVE — must confirm BRIDGE GATE REJECT [check_entry_gates] log lines and zero sub-0.60 trades post-restart. |
| Trade 223/224 below floor — open positions | INFORMATIONAL | Both trades open with conf < 0.60. Entered pre-fix. Will run to existing TP/SL/exit conditions. New gate is entry-only — does not close existing positions. |
| BUY_YES/BUY_NO sign semantics re-check | MEDIUM | Manual spot-check after first open position. No open positions at time of last audit. |
| ESPN/external data intermittent failures | LOW | Dashboard still runs. DNS/TLS errors in dashboard.log. Not blocking trading. |
| next_three_up dashboard feature | LOW | Not available in ESPN scoreboard path. Follow-on task TASK_NEXT_BATTERS_ENRICH_001 documented. Queue when bandwidth allows. |

---

## Blocked on Johnny (user action required)

| Item | What's needed |
|------|--------------|
| Polymarket user/fill stream | Add apiKey, secret, passphrase to .env |
| **Bot restart** | Required to activate BRIDGE_ENTRY_GATE_WIRING_FIX_001. After restart, run CONFIDENCE_GATE_POSTFIX_VERIFY_001. |

---

## Confidence Gate Fix — Evidence Chain

| Step | Task | Status |
|------|------|--------|
| 1. Gate code written | MIN_ENTRY_CONFIDENCE_001 | APPROVED |
| 2. Gate confirmed un-wired (bug) | CONFIDENCE_GATE_RUNTIME_VERIFY_001 | APPROVED |
| 3. Wiring fix applied | BRIDGE_ENTRY_GATE_WIRING_FIX_001 | APPROVED — restart required |
| 4. Post-fix runtime verification | CONFIDENCE_GATE_POSTFIX_VERIFY_001 | **ACTIVE — pending restart** |
