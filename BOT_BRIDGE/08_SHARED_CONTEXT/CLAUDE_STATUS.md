# CLAUDE_STATUS.md — Manager Status Snapshot
## Last reconciled: 2026-04-10 — Live trades now active. Confidence audit (CONFIDENCE_HISTORY_AUDIT_001) has live trade data available for sampling.

---

## System State

### Launcher
- `launch_all.py` — singleton guard active
- 4 children managed: `shadow_engine`, `bot_core`, `dashboard` (port 8900), `resolution_watcher`

### sports_bot_v2 (paper bot)
- Mode: **LIVE TRADES ACTIVE** (as of 2026-04-10 session)
- Bridge: ENABLED (`ENABLE_MODEL_BRIDGE = True`)
- **PnL: +$405.89 realized** (verified against /api/state at time of DASHBOARD_TRUTH_FIXES_001; will shift as live trades settle)
- Authority model: BRIDGE-ONLY (local origination removed by AUTHORITY_SEPARATION_CLEANUP_001)
- Restart: COMPLETE — all risk patches live

### Dashboard
- Running on port 8900
- Accessible at `http://localhost:8900`
- **Truth status: FIXED** — Realized P&L reads authoritative state.pnl.realized, mark_source chip visible on cards, R25 sublabel correct
- **Position card sign semantics (BUY_YES/BUY_NO)**: UNVERIFIED — needs spot-check after next open position

### mlb_model
- Authority: clean (execution_guard.py deleted, ROLLBACK_DISABLE removed)
- Producing today's recs via recommendation_api.py
- resolution_watcher running — marking resolved=True on settled markets

---

## Completed This Session (since last status snapshot)

| Task | Outcome |
|------|---------|
| AUTHORITY_SEPARATION_AUDIT_001 | APPROVED — 8 violations found and scoped for cleanup |
| AUTHORITY_SEPARATION_CLEANUP_001 | PROVISIONAL PASS — code complete, restart required |
| DASHBOARD_TRUTH_REVERIFY_001 | CHANGES_REQUESTED → led to FIXES_001 |
| DASHBOARD_TRUTH_FIXES_001 | APPROVED — 3 dashboard.html defects fixed |

---

## Open Items (not tasks — operator awareness only)

| Item | Severity | Notes |
|------|----------|-------|
| BUY_YES/BUY_NO sign semantics re-check | MEDIUM | Manual spot-check after first open position tonight. No open positions at time of reverify audit. |
| ESPN/external data intermittent failures | LOW | Dashboard still runs. DNS/TLS errors in dashboard.log. Not blocking trading. |
| ~~Session P&L not on dashboard~~ | RESOLVED | SESSION_PNL_DASHBOARD_001 APPROVED — session_start_ts written to state.json, session_pnl computed from DB. |

---

## Blocked on Johnny (user action required)

| Item | What's needed |
|------|--------------|
| Polymarket user/fill stream | Add apiKey, secret, passphrase to .env |
| ~~Bot restart~~ | ✅ DONE — restarted 2026-04-10, all patches live. Confirmed by PROCESS_CLEANUP_VERIFY_001. |

---

## Deferred (not tonight-critical)

| Item | Why deferred |
|------|-------------|
| Bankroll-aware sizing (RISK_PCT_PER_TRADE) | High value improvement but not a correctness risk tonight |
| Min entry confidence threshold | Strategy tuning — can wait |
| Misplaced BOT_BRIDGE artifacts (SAFE_MOVES_ONLY_001) | Cosmetic — 8 files in wrong root, no runtime impact |
| BOT_BRIDGE naming/closure normalization | Housekeeping |
| Spread/totals model expansion | Long-term roadmap |
