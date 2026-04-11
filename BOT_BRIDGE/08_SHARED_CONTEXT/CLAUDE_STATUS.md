# CLAUDE_STATUS.md — Manager Status Snapshot
## Last reconciled: 2026-04-10 — Board reconciliation: MARK_FALLBACK trace, FIX, and VERIFY all closed. 0 ACTIVE tasks. Mark fallback reliability fix live. Two operator actions still required (pyc + cold restart; browser hard refresh).

---

## ⚠ OPERATOR ACTIONS REQUIRED

**1. Delete `__pycache__/bot_core.cpython-*.pyc` and cold-restart the stack.**
Until this is done, confidence gate, cooldown persistence, session PnL fix, and dupe-slug fix are NOT executing regardless of what code is patched.
See: `08_SHARED_CONTEXT/OPERATOR_ACTION_REQUIRED_001.md`

**2. Browser hard refresh (`Ctrl+Shift+R`) on the dashboard.**
POSITION_SIDE_SEMANTICS_MERGE_FIX_001 is live in dashboard.html — no server restart needed, but the browser must reload the file.

---

## System State

### Launcher
- `launch_all.py` — singleton guard active
- 4 children managed: `shadow_engine`, `bot_core`, `dashboard` (port 8900), `resolution_watcher`

### sports_bot_v2 (paper bot)
- Mode: LIVE TRADES ACTIVE
- Bridge: ENABLED (`ENABLE_MODEL_BRIDGE = True`)
- **Confidence gate: PATCHED IN SOURCE — awaiting cold restart** — `bot_core.py` lines 504–525 patched. Stale `__pycache__/bot_core.cpython-*.pyc` must be deleted before patch executes.
- **Tonight's session: -$159.54 on 40 closed trades.** 31/42 (73.8%) sub-0.60 confidence. Gate failure was primary cause.
- **Currently open trades (from last state.json read):**
  - #276: BUY_YES mlb-tex-lad entry=0.2412
  - #277: BUY_YES mlb-hou-sea entry=0.3819
- **Market cooldown: PATCHED IN SOURCE — awaiting cold restart** — MARKET_COOLDOWN_PERSIST_001 DONE.
- **Session PnL: PATCHED IN SOURCE — awaiting cold restart** — SESSION_PNL_TRUE_START_FIX_001 DONE.
- **Min entry price gate: PATCHED** — MIN_ENTRY_PRICE_GATE_001 DONE.
- **TP math: PATCHED** — TP_NEAR_RESOLUTION_CAP_FIX_001 DONE.
- **Dupe-slug bypass: PATCHED** — BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001 DONE.
- **Mark fallback reliability: LIVE** — MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001 DONE. dashboard_server.py patched. Dashboard restart confirmed.

### Dashboard
- Running on port 8900
- **Side semantics: FIXED** — POSITION_SIDE_SEMANTICS_MERGE_FIX_001 DONE. `renderUnifiedPositions()` no longer overwrites `side`, `backed_team`, `faded_team`, `entry_px`, `qty`, `id` from stale cache. **Hard refresh required.**
- **Games-tab position lookup: FIXED** — `renderGamesTab()` slug-key date-suffix mismatch fixed. Open positions now appear in Games tab after hard refresh.
- Truth status: FIXED — realized PnL authoritative, mark_source chip correct, R25 sublabel correct, side/team semantics correct.
- At-bat upgrade: LIVE (DASHBOARD_LIVE_ATBAT_POLISH_001 PROVISIONAL PASS)
- Mark fallback chain: RESOLVED — trace DONE (PARTIAL PASS), fix DONE (APPROVED), verify DONE (PROVISIONAL PASS)

### mlb_model
- Authority: clean (execution_guard.py deleted, ROLLBACK_DISABLE removed)
- Producing today's recs via recommendation_api.py
- resolution_watcher running

---

## Completed This Session (2026-04-10)

| Task | Outcome |
|------|---------|
| MARK_SOURCE_FALLBACK_RELIABILITY_VERIFY_001 | PROVISIONAL PASS — stream-mark authority confirmed in healthy case. Fallback path not live-fired in short window. |
| MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001 | APPROVED — dashboard_server.py `_has_fresh_stream_mark` guard added. Stream marks stay primary. Dashboard restarted. |
| MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001 | PARTIAL PASS — mark-source chain documented. "max down" not found. REST fallback active due to upstream freshness, not UI bug. |
| POSITION_SIDE_SEMANTICS_MERGE_FIX_001 | APPROVED — dashboard.html renderUnifiedPositions() and renderGamesTab() patched. Browser hard refresh required. |
| POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001 | APPROVED — root cause confirmed at line 1139, stale full-object spread. |
| SESSION_PNL_TRUE_START_FIX_001 | APPROVED — bot_core.py patched; session_start_ts persists across restarts. |
| MARKET_COOLDOWN_PERSIST_001 | APPROVED — bot_core.py patched; cooldown expiry timestamps persist across restarts. |
| BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001 | APPROVED — bot_core.py bridge loop deduplication patched. |
| TP_NEAR_RESOLUTION_CAP_FIX_001 | APPROVED — core/risk.py TP capped at 0.97 for near-resolution entries. |
| MIN_ENTRY_PRICE_GATE_001 | APPROVED — core/risk.py min entry price gate added. |

---

## Active Tasks

_None._

## Queued Tasks

_None — all previously queued tasks are DONE._

---

## Open Items (not tasks)

| Item | Severity | Notes |
|------|----------|-------|
| **Pyc cache delete + cold restart** | CRITICAL OPERATOR ACTION | Activates: confidence gate, min price gate, cooldown persistence, session PnL fix, dupe-slug fix |
| **Browser hard refresh** | OPERATOR ACTION | Activates: side/team semantics fix, Games-tab position lookup fix |
| BUY_YES/BUY_NO sign semantics re-check | LOW | Deprioritized; semantic identity fields are now authoritative post-merge fix |
| next_three_up dashboard feature | LOW | Deferred — ESPN data unavailable |
| Polymarket user/fill stream | BLOCKED | Requires apiKey, secret, passphrase in .env |

---

## Blocked on Johnny (user action required)

| Item | What's needed |
|------|--------------|
| **Pyc cache clear + cold restart** | `del __pycache__/bot_core.cpython-*.pyc` then cold restart via launch_all.py |
| **Dashboard hard refresh** | `Ctrl+Shift+R` in browser — picks up POSITION_SIDE_SEMANTICS_MERGE_FIX_001 |
| **Gate verification after restart** | Confirm `BRIDGE GATE REJECT [check_entry_gates]` fires before any sub-0.60 or sub-MIN_ENTRY_PRICE entry |
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
| 6. Min price gate added | MIN_ENTRY_PRICE_GATE_001 | APPROVED — in source |
| 7. Dupe-slug bypass fixed | BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001 | APPROVED — in source |
| 8. Clear pyc + cold restart | OPERATOR_ACTION_REQUIRED_001 | **PENDING — operator must do this** |
