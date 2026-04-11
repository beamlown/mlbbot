# CLAUDE_STATUS.md — Manager Status Snapshot
## Last reconciled: 2026-04-10 — Postfix verify PARTIAL PASS. Two gate bypass issues found. Dashboard audit task opened.

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
- **Confidence gate: PARTIALLY ACTIVE** — Patch in source (BRIDGE_ENTRY_GATE_WIRING_FIX_001 APPROVED). Gate confirmed firing at first post-patch restart (3 rejections at 18:29:31 CDT). Two bypass paths found by CONFIDENCE_GATE_POSTFIX_VERIFY_001 (PARTIAL PASS): **(A) duplicate intent bypass** — trade 236 (conf=0.56) opened via second slug instance not rejected; **(B) stale pyc cache** — trade 238 (conf=0.4639) opened at second restart with zero gate rejections. **BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001 fix task required. Clear `__pycache__/bot_core.cpython-*.pyc` + clean restart required.**
- Currently open trades: 223 (conf=0.3353, pre-fix), 237 (conf=0.6429, valid), 238 (conf=0.4639, Issue B bypass). Bot at **MAX_CONCURRENT_TRADES (3/3)** — all loops BRIDGE SKIP. No new entries until a position closes.

### Dashboard
- Running on port 8900
- At-bat upgrade live: dominant score hierarchy, count chips, batter/pitcher identity, last-play text (DASHBOARD_LIVE_ATBAT_POLISH_001 PROVISIONAL PASS)
- **Note:** dashboard_server.py was modified by ATBAT task — if not in Flask debug mode, dashboard_server.py process restart needed for current_batter/pitcher fields to appear
- **Truth status: FIXED** — Realized P&L authoritative, mark_source chip visible, R25 sublabel correct
- **Display issues under audit** — DASHBOARD_MARK_SOURCE_AND_GUARD_MESSAGE_AUDIT_001 ACTIVE. Operator reported: (1) position cards showing `mark REST` chip (REST fallback pricing) instead of live stream marks; (2) "max down" style warning message when runtime guard reasons are `micro_depth_too_low` and `micro_spread_too_wide`. Worker audit pending.

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
| BRIDGE_ENTRY_GATE_WIRING_FIX_001 | APPROVED — patch applied to bot_core.py; py_compile PASS |
| DASHBOARD_LIVE_ATBAT_POLISH_001 | PROVISIONAL PASS — at-bat UI upgraded; next_three_up deferred (data unavailable in ESPN path) |
| CONFIDENCE_GATE_POSTFIX_VERIFY_001 | PARTIAL PASS — gate confirmed at restart 1 (3 rejections); 2 bypass paths found (duplicate intent, stale pyc). Fix tasks required. |

---

## Open Items (not tasks — operator awareness only)

| Item | Severity | Notes |
|------|----------|-------|
| **Clear pyc cache + clean restart** | HIGH | `__pycache__/bot_core.cpython-*.pyc` likely stale — second restart loaded pre-patch bytecode. Delete pyc, restart, re-verify gate. |
| **BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001** | HIGH | Fix task needed — add per-iteration rejected-slug set to bridge loop so duplicate slug intents can't bypass gate on second iteration. |
| **Dashboard display issues** | MEDIUM | DASHBOARD_MARK_SOURCE_AND_GUARD_MESSAGE_AUDIT_001 ACTIVE — mark REST chip + max-down warning audit in progress. |
| Trade 238 below floor — open | INFORMATIONAL | Opened via stale-pyc bypass (conf=0.4639). Running to existing exit conditions. Gate is entry-only — not affected. |
| Trade 223 below floor — open | INFORMATIONAL | Pre-fix, conf=0.3353. Running to existing exit conditions. |
| BUY_YES/BUY_NO sign semantics re-check | MEDIUM | Manual spot-check after first open position closes and a new one opens. |
| ESPN/external data intermittent failures | LOW | Dashboard still runs. DNS/TLS errors in dashboard.log. Not blocking trading. |
| next_three_up dashboard feature | LOW | Not available in ESPN scoreboard path. Follow-on task TASK_NEXT_BATTERS_ENRICH_001 documented. Queue when bandwidth allows. |

---

## Blocked on Johnny (user action required)

| Item | What's needed |
|------|--------------|
| Polymarket user/fill stream | Add apiKey, secret, passphrase to .env |
| **pyc cache clear** | Delete `__pycache__/bot_core.cpython-*.pyc` from sports_bot_v2 directory, then restart bot_core cleanly to ensure patched code is loaded |

---

## Confidence Gate Fix — Evidence Chain

| Step | Task | Status |
|------|------|--------|
| 1. Gate code written | MIN_ENTRY_CONFIDENCE_001 | APPROVED |
| 2. Gate confirmed un-wired (bug) | CONFIDENCE_GATE_RUNTIME_VERIFY_001 | APPROVED |
| 3. Wiring fix applied | BRIDGE_ENTRY_GATE_WIRING_FIX_001 | APPROVED |
| 4. Post-fix runtime verification | CONFIDENCE_GATE_POSTFIX_VERIFY_001 | PARTIAL PASS — 2 bypass paths found, fix tasks required |
| 5. Duplicate-intent bypass fix | BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001 | NOT OPENED — queued |
| 6. pyc cache clear + re-verify | — | Operator action required |
