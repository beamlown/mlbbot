# CLAUDE_TASK_BOARD.md — Manager Task Board
## Last updated: 2026-04-10 — CONFIDENCE_GATE_POSTFIX_VERIFY_001 closed PARTIAL PASS. DASHBOARD_MARK_SOURCE_AND_GUARD_MESSAGE_AUDIT_001 opened. 1 ACTIVE task.

---

## Policy Reminders
- Max 3 ACTIVE tasks at once
- No two ACTIVE tasks may touch the same file
- No two ACTIVE tasks on same subsystem unless explicitly non-overlapping
- New conflicting tasks → QUEUED, not ACTIVE
- Each task must have: task_id, priority, subsystem, allowed_files, status
- Every ACTIVE task must have a brief in 05_INBOX_FROM_MANAGER

---

## ACTIVE

| task_id | title | priority | subsystem | allowed_files | status |
|---------|-------|----------|-----------|---------------|--------|
| DASHBOARD_MARK_SOURCE_AND_GUARD_MESSAGE_AUDIT_001 | Audit mark REST chip and max-down warning message — identify display chain root causes | MEDIUM | read-only dashboard audit | runtime/state.json, logs/dashboard.log, logs/dashboard_err.log, dashboard.html, dashboard_server.py | ACTIVE — awaiting worker execution. Brief in 05_INBOX. |

---

## QUEUED

_None._

---

## BLOCKED

| task_id | title | reason | unblocked_by |
|---------|-------|--------|--------------|
| EXIT_GAME_AWARE_001 | Game-aware exit gate (HOLD_TO_RESOLUTION) | SUPERSEDED — original gate caused 3 stuck trades. Re-scoped as EXIT_GAME_AWARE_002, which is now DONE. | N/A — superseded |
| RUNTIME_USER_STREAM_AUTH_UNBLOCK_001 | Unblock Polymarket user/fill stream auth | Missing apiKey, secret, passphrase in .env — user must supply credentials. No worker can unblock this. | User action required |

---

## DONE

| task_id | title | outcome | allowed_files |
|---------|-------|---------|---------------|
| CONFIDENCE_GATE_POSTFIX_VERIFY_001 | Verify check_entry_gates() is live post-restart: confirm gate rejections and no sub-0.60 bridge entries | PARTIAL PASS 2026-04-10 — Gate confirmed at restart 1 (3 rejections). Two bypass paths found: (A) duplicate intents — trade 236 conf=0.56 slipped through second iteration; (B) stale pyc cache at restart 2 — trade 238 conf=0.4639 opened with zero gate rejections. Fix tasks required: BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001 + pyc cache clear + clean restart. | bot logs (read-only), trades_sports.db (SELECT only), bot_core.py (read-only) |
| BRIDGE_ENTRY_GATE_WIRING_FIX_001 | Wire check_entry_gates() into live bridge entry path | APPROVED 2026-04-10 — bot_core.py lines 507-517 patched; py_compile PASS. Postfix verify: PARTIAL PASS (see above). | `bot_core.py` |
| CONFIDENCE_GATE_RUNTIME_VERIFY_001 | Verify runtime enforcement of MIN_ENTRY_CONFIDENCE=0.60 against post-restart live trades | APPROVED 2026-04-10 — real bug confirmed (bypass path). Trades 223/224 confirmed post-restart. Gate never called. Root cause: bridge path skipped check_entry_gates(). | read-only |
| CONFIDENCE_HISTORY_AUDIT_001 | Historical confidence audit — recent recommendations/trades vs new 0.60 hard floor | APPROVED 2026-04-10 — 178 trades + 41,248 shadow recs audited. 69% of historical trades below floor. Bimodal distribution documented. 0.60 floor confirmed realistic. | read-only |
| DASHBOARD_LIVE_ATBAT_POLISH_001 | Upgrade live game cards with at-bat state, next-three-up, baseball-first hierarchy | PROVISIONAL PASS 2026-04-10 — score/count/batter/last-play implemented. next_three_up not available in ESPN scoreboard path — follow-on task TASK_NEXT_BATTERS_ENRICH_001 documented. | `dashboard.html`, `dashboard_server.py` |
| LIVE_CARD_BASEBALL_SEMANTICS_001 | LIVE card phrasing → baseball semantics (backed/faded vs WIN/LOSE) | APPROVED (ratified) 2026-04-10 — dashboard.html only. Self-directed change by worker without brief; content correct, process violation noted in review. | `dashboard.html` |
| PROCESS_CLEANUP_VERIFY_001 | Verify process topology is clean after restart | APPROVED 2026-04-10 — 6/6 criteria PASS. System clean at task start. No kills required. PIDs confirmed: bot_core 24800, dashboard_server 29620, resolution_watcher 47560, recommendation_api 44152. | read-only / process inspect only |
| MIN_ENTRY_CONFIDENCE_001 | Hard confidence floor gate (0.60) — first gate in check_entry_gates() waterfall | APPROVED 2026-04-10 — gate added to risk.py, .env updated. NOTE: gate was not wired into bridge path until BRIDGE_ENTRY_GATE_WIRING_FIX_001. | `core/risk.py`, `.env` |
| SESSION_EXPOSURE_CAP_001 | MAX_TOTAL_COMMITTED_USD=150 dollar ceiling on total open exposure | APPROVED 2026-04-10 — gate added after per-market gate in risk.py | `core/risk.py`, `.env` |
| SESSION_PNL_DASHBOARD_001 | Session P&L in /api/state bankroll block | APPROVED 2026-04-10 — session_start_ts written to state.json, session_pnl computed from DB | `bot_core.py`, `dashboard_server.py` |
| BANKROLL_AWARE_SIZING_001 | Bankroll-aware sizing (3% of bankroll, $50 max, $10 floor) | APPROVED 2026-04-10 — replaces fixed $50 base with bankroll * 0.03; MAX_POSITION_SIZE_USD lowered to $50 | `core/paper_exec.py`, `.env` |
| DASHBOARD_TRUTH_FIXES_001 | Fix 3 dashboard.html truth defects found by REVERIFY audit | APPROVED 2026-04-10 — Realized P&L now reads authoritative state.pnl.realized ($405.89); mark_source chip added to position cards; R25 sublabel uses r25.sample_size. dashboard.html only. | `dashboard.html` |
| DASHBOARD_TRUTH_REVERIFY_001 | Re-verify dashboard display truth end-to-end against live endpoints | CHANGES_REQUESTED 2026-04-10 — 3 failures found (Realized P&L mis-sourced, mark_source not displayed, R25 sublabel zero). Resolved by DASHBOARD_TRUTH_FIXES_001. BUY_YES/BUY_NO sign semantics unverified (no open positions at audit time — needs spot-check after restart). | read-only |
| AUTHORITY_SEPARATION_CLEANUP_001 | Remove local MLB origination from sports_bot_v2; decouple execution gating from mlb_model | PROVISIONAL PASS 2026-04-10 — All acceptance criteria met. Code removals verified (grep confirms zero residual symbols). execution_guard.py deleted. VCS caveat: mlb_model/signal_base paths untracked so commit is partial; runtime behavior unaffected. **Restart required.** | `bot_core.py`, `core/signal_base.py`, `mlb_model/integration/recommendation_api.py`, `mlb_model/core/execution_guard.py` |
| AUTHORITY_SEPARATION_AUDIT_001 | Audit authority separation violations across 5 files | APPROVED 2026-04-10 — 8 violations found (4 in sports_bot_v2 gated/inactive, 4 in mlb_model active). model_bridge.py and bot_core.py bridge path confirmed clean. Cleanup scope authorized. | read-only |
| RISK_AND_TP_AUDIT_001 | Final risk system audit document | APPROVED 2026-04-10 — RISK_MANAGEMENT_FINAL_AUDIT_001.md written. 12/12 checks PASS. 6 gaps documented (2 HIGH open). | `08_SHARED_CONTEXT/` only |
| RISK_AND_TP_VERIFY_001 | End-to-end verification: TP/SL, sizing, held-side pricing, bankroll all agree | APPROVED — 12/12 PASS. DB↔dashboard exact match $351.91 at time of audit. SYSTEM VERIFIED. 2026-04-10 | read-only |
| BANKROLL_SESSION_RULES_001 | Enforce correct bankroll/session/available-cash accounting | APPROVED — available_cash clamped to 0 + WARNING; /api/bankroll lifetime PnL fix. BANKROLL_ACCOUNTING_SPEC_001.md written. 2026-04-10 | `dashboard_server.py`, `core/paper_exec.py` |
| EXECUTION_RISK_MONITOR_001 | Harden exit loop: empty-OB warnings, dummy-market warnings, error logging | APPROVED — 4 exit loop hardening fixes. 2026-04-10 | `bot_core.py` |
| POSITION_SIZING_RULES_001 | Define and enforce per-trade sizing: formula, caps, confidence tiers, liquidity gate | APPROVED — docs only, 4/6 invariants confirmed, 2 HIGH gaps deferred to BANKROLL_SESSION_RULES_001. SIZING_RULES_SPEC_001.md written. 2026-04-10 | `core/paper_exec.py`, `core/risk.py` |
| SESSION_LOSS_CAP_001 | Add per-session and daily max-loss kill switches to block new entries | APPROVED — SESSION_MAX_LOSS_USD + DAILY_MAX_LOSS_USD env-gated, default 0 (disabled). bot_core.py only. 2026-04-10 | `bot_core.py` |
| TP_SL_SCHEMA_NORMALIZATION_001 | Normalize TP/SL/committed/max_loss to canonical functions in core/risk.py | APPROVED — conservative schema cleanup, no threshold changes. 2026-04-10 | `core/risk.py`, `core/paper_exec.py`, `core/types.py` |
| MARKET_RESOLVED_DB_FIELDS_001 | Fix market_resolved close path — add reason_close and ts_close to DB payload | APPROVED — commit d8fc4bf. 2026-04-10 | `bot_core.py` |
| RISK_PIPELINE_AUDIT_001 | Audit full risk pipeline end-to-end | APPROVED — 5 gaps found, 1 broken invariant. RISK_PIPELINE_AUDIT_REPORT_001.md. 2026-04-10 | read-only |
| EXIT_GAME_AWARE_002 | Hold-to-resolution gate — suppress near_resolution exit until watcher confirms settlement | APPROVED — gate live 2026-04-10. | `bot_core.py` |
| RESOLUTION_WATCHER_INTEGRATE_001 | Wire resolved_markets.json into bot_core exit loop — force-close on resolution | APPROVED — force-close wired before check_exit(). 2026-04-10 | `bot_core.py` |
| RESOLUTION_WATCHER_BUILD_001 | Build integration/resolution_watcher.py — poll Polymarket for market resolution | APPROVED — integration/ package created, polls Gamma API. 2026-04-10 | `integration/__init__.py`, `integration/resolution_watcher.py` |
| SL_COOLDOWN_001 | Market cooldown after stop_loss and gap_stop exits | APPROVED — stop_loss 1800s + gap_stop 3600s live. 2026-04-10 | `bot_core.py` |
| EXIT_PARAMS_TIGHTEN_001 | Tighten exit thresholds — TP 0.40, SL 0.12, NRP 0.97, trailing 0.10/0.12 | APPROVED — .env verified. 2026-04-10 | `.env` |
| BOT_DATE_GATE_DEFENSE_001 | Date gate: reject non-today slugs in local MLB origination path | APPROVED | `bot_core.py` |
| DASHBOARD_LIVE_STRIP_FIXES_001 | Dashboard live strip fixes — committed tile id, bankroll MTM, feed status wording | APPROVED — commit 7b33f18 | `dashboard.html` |
| STALE_MARK_REST_FALLBACK_001 | REST polling fallback for stale marks in dashboard_server.py | APPROVED + RUNTIME VERIFIED — commit b31b548. mark_source=rest_fallback confirmed live. | `dashboard_server.py` |
| DASHBOARD_REDESIGN_LIVE_SMOKE_003 | Dashboard redesign — live smoke (round 3) | APPROVED — REST fallback verified directly. Smoke series DONE. | _(none — read only)_ |
| LIVE_CARD_PNL_SIGN_REGRESSION_001 | BUY_NO unrealized P&L sign fix | APPROVED — sign verified PASS for all 3 open positions at time of test | _(none — runtime only)_ |
| DASHBOARD_REDESIGN_LIVE_SMOKE_002 | Dashboard redesign — live smoke test (round 2) | CHANGES_REQUESTED → resolved by SMOKE_003 + REST fallback. | _(none — read only)_ |
| DASHBOARD_REDESIGN_LIVE_SMOKE_001 | Dashboard redesign — live smoke test | FAIL (sign regression) → resolved by LIVE_CARD_PNL_SIGN_REGRESSION_001. | _(none — read only)_ |
| DASHBOARD_REDESIGN_AUDIT_001 | Dashboard redesign — audit against spec | APPROVED | _(none)_ |
| DASHBOARD_REDESIGN_VERIFY_001 | Dashboard redesign — truth preservation and usability verification | APPROVED (PASS) | _(none)_ |
| DASHBOARD_PERFORMANCE_POLISH_001 | Dashboard redesign — performance, flicker elimination, visual polish | APPROVED — commit a19f421 | `dashboard.html` |
| DASHBOARD_POSITIONS_HISTORY_SYSTEM_001 | Dashboard redesign — secondary tabs | APPROVED — commits fa12342 + f9d7f25 | `dashboard.html` |
| DASHBOARD_LIVE_COMMAND_CENTER_001 | Dashboard redesign — LIVE tab | APPROVED — commit 2e7bfcc | `dashboard.html` |
| DASHBOARD_REDESIGN_SHELL_001 | Dashboard redesign — shell, layout, 5-tab nav | APPROVED — commit 552686f | `dashboard.html` |
| DASHBOARD_REDESIGN_ARCH_001 | Dashboard redesign — architecture spec and payload mapping | APPROVED — DASHBOARD_REDESIGN_SPEC_001.md written | _(none)_ |
| EXECUTION_HELD_SIDE_SEMANTICS_001 | Normalize execution-side held-contract semantics | APPROVED — commit 2dbb3fc | `core/risk.py`, `core/paper_exec.py` |
| BASEBALL_POSITION_SEMANTICS_INCIDENT_001 | Fix BUY_NO dashboard math | APPROVED | `dashboard_server.py`, `dashboard.html` |
| PRICE_SOURCE_SINGLE_AUTHORITY_001 | Single price-source authority audit | APPROVED | read-only audit |
| LIVE_MODEL_REACTION_REVERIFY_001 | Re-verify live model reaction cadence | PARTIAL (needs richer live window) | read-only |
| LIVE_MODEL_CADENCE_TUNING_001 | Live model reaction cadence tuning | APPROVED | `mlb_model/` |
| LIVE_MODEL_REACTION_AUDIT_001 | Live model reaction audit | APPROVED | read-only audit |
| LIVE_SESSION_VERIFY_002 | Live session end-to-end verify (round 2) | APPROVED | read-only |
| PAPER_RESET_AND_CLEAN_START_001 | Reset open paper trades, clean session start | APPROVED | DB ops only |
| LIVE_SESSION_VERIFY_001 | Live session end-to-end verify | SUPERSEDED (wrong target 127.0.0.1:8000) | read-only |
| LIVE_FEED_STATUS_POLISH_001 | Live feed status UI polish | CLAIMED (artifacts misplaced in wrong root) | `dashboard.html` |
| REALTIME_GAME_STATE_PUSH_001 | Push live game state to dashboard | APPROVED | `dashboard_server.py`, `dashboard.html` |
| VERIFY_REALTIME_MARKET_STREAM_STAGE1_FINAL | Verify polymarket realtime stream Stage 1 final | APPROVED | read-only |
| MARKET_STREAM_LIST_MESSAGE_FIX_001 | Fix market stream parser crash on list-shaped messages | APPROVED | `core/polymarket_stream.py` |
| MARKET_STREAM_DEBUG_STATUS_FIX_001 | Fix market stream debug status display | APPROVED | `dashboard_server.py` |
| VERIFY_REALTIME_MARKET_STREAM_STAGE1_002 | Verify realtime market stream Stage 1 (round 2) | APPROVED | read-only |
| REALTIME_MARKET_STREAM_TRACKING_FIX_001 | Fix realtime market stream token tracking | APPROVED | `core/polymarket_stream.py` |
| REALTIME_MARKET_STREAM_DIAG_001 | Realtime market stream diagnostics | APPROVED | read-only |
| DISCOVERY_TOKEN_IDS_001 | Discover token IDs for active markets | APPROVED | read-only |
| RUNTIME_DEP_UNBLOCK_001 | Unblock runtime dependency issues | APPROVED | env/deps |
| REALTIME_MARKET_EXECUTION_DISCOVERY_001 | Realtime market execution discovery | APPROVED | read-only |
| VERIFY_ODDS_API_BUDGET_ENFORCEMENT_001 | Verify odds API budget enforcement | APPROVED | read-only |
| ODDS_API_BUDGET_ENFORCEMENT_001 | Odds API budget enforcement | APPROVED | `core/model_bridge.py` |
| RUNTIME_ACTIVATE_REALTIME_STAGE2_001 | Activate realtime dashboard Stage 2 at runtime | APPROVED | runtime ops |
| VERIFY_REALTIME_DASHBOARD_STAGE2_001 | Verify realtime dashboard Stage 2 | APPROVED | read-only |
| REALTIME_DASHBOARD_ARCH_STAGE2_001 | Realtime dashboard architecture Stage 2 | APPROVED | `dashboard_server.py`, `core/state_hub.py` |
| DASHBOARD_LIVE_SEMANTICS_001 | Dashboard live semantics normalization | APPROVED | `dashboard_server.py`, `dashboard.html` |
| MODEL_GATING_SPLIT_PROOF_001 | Model gating split proof | APPROVED | read-only |
| EXECUTION_METADATA_PERSISTENCE_PROOF_001 | Execution metadata persistence proof | APPROVED | read-only |
| VERIFY_EXECUTION_CONTRACT_BIND_001 | Verify execution contract bind | APPROVED | read-only |
| EXECUTION_CONTRACT_BIND_001 | Execution contract bind — bot_core consumes full bridge fields | APPROVED | `bot_core.py` |
| VERIFY_BRIDGE_CONTRACT_001 | Verify bridge contract | APPROVED | read-only |
| BRIDGE_CONTRACT_001 | Bridge contract — model_bridge passes 50+ rich fields | APPROVED | `core/model_bridge.py` |
| VERIFY_MODEL_AUTHORITY_001 | Verify model authority separation | APPROVED | read-only |
| MODEL_AUTHORITY_001 | Model authority separation — ALLOW_LOCAL_MLB_ORIGINATION=0 | APPROVED | `bot_core.py`, `.env` |
| DASHBOARD_TRUTH_CHAIN_CLOSE_001 | Dashboard truth chain close verification | APPROVED | read-only |
| DUPLICATE_ENTRY_LIVE_REAUDIT_001 | Duplicate entry live reaudit | APPROVED | read-only |
| R25_PROOF_FIX_001 | Fix R25 win rate proof | APPROVED | `dashboard_server.py` |
| SYSTEM_BUG_AUDIT_001 | System bug audit | APPROVED | read-only |
| DASHBOARD_V2_ROUTE_001 | Dashboard V2 route fix | APPROVED | `dashboard_server.py` |
| VERIFY_DASHBOARD_V2_001 | Verify dashboard V2 | APPROVED | read-only |
| DASHBOARD_V2_001 | Dashboard V2 redesign | APPROVED | `dashboard.html`, `dashboard_server.py` |
| DASHBOARD_RESTORE_BASEBALL_MONITOR_001 | Restore baseball monitor | APPROVED | `dashboard.html` |
| DASHBOARD_HIERARCHY_FIX_001 | Dashboard hierarchy fix | APPROVED | `dashboard.html` |
| DASHBOARD_LIVE_GAME_MONITOR_001 | Dashboard live game monitor | APPROVED | `dashboard.html` |
| DASHBOARD_STYLE_FUN_001 | Dashboard style polish | APPROVED | `dashboard.html` |
| DASHBOARD_POLISH_001 | Dashboard polish | APPROVED | `dashboard.html` |
| VERIFY_DASHBOARD_TRUTH_002 | Verify dashboard truth | APPROVED | read-only |
| DASHBOARD_TRUTH_002 | Dashboard truth fix | APPROVED | `dashboard_server.py` |
| INCIDENT_TOPOLOGY_FINAL_001_ADDENDUM | Incident topology final addendum | APPROVED | read-only |
| INCIDENT_TOPOLOGY_FINAL_001 | Incident topology final | APPROVED | `launch_all.py` |
| INCIDENT_STATE_RESYNC_001 | Incident state resync | APPROVED | DB ops |
| INCIDENT_DB_REMEDIATION_001 | Incident DB remediation | APPROVED | DB ops |
| INCIDENT_DB_VERIFY_001 | Incident DB verify | APPROVED | read-only |
| INCIDENT_PROCESS_DB_001 | Incident process DB | APPROVED | process containment |
| VERIFY_DUPLICATE_ENTRY_001 | Verify duplicate entry fix | APPROVED | read-only |
| DUPLICATE_ENTRY_FIX_001 | Fix duplicate paper trade entry — DB atomic dedup + NULL return | APPROVED | `core/db.py`, `bot_core.py` |
| SYSTEM_UNIFY_001 | Unify dashboard truth — execution positions only | APPROVED | `dashboard.html` |
| DASH_016 | Trade log: team name, USD size, command bar win rate binding | APPROVED | `dashboard.html` |
| RISK_001 | Confidence-tiered position sizing | APPROVED | `core/paper_exec.py`, `.env` |
| DASH_015 | Position card: WIN/LOSE direction, TP/SL/Size boxes | APPROVED | `dashboard.html` |
| DASH_014 | Win rate for paper trades + fix BUY_NO TP/SL | APPROVED | `dashboard_server.py` |
| DASH_013 | Fix shadow feed ticker — inning shown for pre-game recs | APPROVED | `dashboard.html` |
| DASH_012 | Fix game status chip — LIVE shown for unstarted games | APPROVED | `dashboard.html` |
| DASH_011 | Remove resolved paper trades from Positions panel | APPROVED | `dashboard.html` |
| DASH_010 | Fix section title and badge count | APPROVED | `dashboard.html` |
| DASH_009 | Fix resolved paper trade cards — PnL, Current price, team name | APPROVED | `dashboard_server.py` |
| VERIFY_STABILIZE_001 | Fix stale shadow ghost positions | APPROVED | `launch_all.py`, `dashboard_server.py` |
| LAUNCH_002 | Add dashboard_server.py to launch_all.py | APPROVED | `launch_all.py` |
| DASH_008 | Remove hardcoded TP/SL JS constants | APPROVED | `dashboard.html` |
| DASH_006 | Fix TP/SL — compute server-side per trade | APPROVED | `dashboard_server.py` |
| DASH_007 | Simplify drawer — remove Markets and Signals tabs | APPROVED | `dashboard.html` |
| BRIDGE_ENABLE_001 | Re-enable model bridge kill switch | APPROVED | `core/model_bridge.py` |
| DASH_005 | Add bridge_enabled field to /api/state | APPROVED | `dashboard_server.py` |
| DASH_004 | Merge HUD + header into single command bar | APPROVED | `dashboard.html` |
| DASH_003 | Replace scoreboard with compact games ticker | APPROVED | `dashboard.html` |
| DASH_002 | Compact position cards — remove visual bloat | APPROVED | `dashboard.html` |
| MLB_002 | Fix live game abbreviation alias gaps | APPROVED | `mlb_model/integration/recommendation_api.py` |
| MLB_001 | Diagnose live market discovery mismatch | APPROVED | `mlb_model/integration/recommendation_api.py` |
| SHADOW_001 | Add shadow dollar PnL, entry/current price, TP/SL | APPROVED | `dashboard.html`, `dashboard_server.py` |
| PAPER_BRIDGE_003 | Live gate verification | APPROVED | `core/model_bridge.py` |
| PAPER_BRIDGE_002 | Persist source='model_bridge' | APPROVED | multiple |
| BRIDGE_FIX_001 | Add cap + per-open re-fetch to bridge section | APPROVED | `bot_core.py` |
| LAUNCH_FIX_001B | Fix PID guard — ctypes liveness check | APPROVED | `launch_all.py` |
| LAUNCH_001 | Concurrent launcher with watchdog | APPROVED | `launch_all.py`, `core/model_bridge.py` |
| DASHBOARD_REWORK_001 | Dashboard redesign | APPROVED | `dashboard.html` |

---

## Conflict Map

| File | Locked by |
|------|-----------|
| runtime/state.json, logs/dashboard.log, dashboard.html, dashboard_server.py | DASHBOARD_MARK_SOURCE_AND_GUARD_MESSAGE_AUDIT_001 (read-only, no exclusive lock) |
| All other files | UNLOCKED |

---

## System state (2026-04-10 — post gate postfix verify)

- **Realized PnL: $405.89** (last verified at DASHBOARD_TRUTH_FIXES_001)
- **Dashboard truth: FIXED** — Realized P&L authoritative, mark_source chip live, R25 sublabel corrected
- **At-bat dashboard: UPGRADED** — DASHBOARD_LIVE_ATBAT_POLISH_001 PROVISIONAL PASS. count chips, dominant score, batter/pitcher identity live.
- **Authority separation: CODE COMPLETE** — local origination removed (AUTHORITY_SEPARATION_CLEANUP_001 PROVISIONAL PASS)
- **Risk pack: VERIFIED** — 12/12 checks pass. All 4 risk/sizing tasks APPROVED.
- **Confidence gate: PARTIALLY ACTIVE** — BRIDGE_ENTRY_GATE_WIRING_FIX_001 patch in source. Gate fires at first restart. Two bypass paths identified (duplicate intent, stale pyc). **BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001 fix task needed. Clear pyc cache + clean restart required.**
- **Currently open trades: 223 (conf=0.3353), 237 (conf=0.6429), 238 (conf=0.4639)** — 223 pre-fix; 237 valid; 238 Issue B bypass. Bot at MAX_CONCURRENT_TRADES (3/3). All loops show BRIDGE SKIP.
- **Dashboard display issues under audit** — DASHBOARD_MARK_SOURCE_AND_GUARD_MESSAGE_AUDIT_001 ACTIVE. mark REST chip and max-down warning message symptoms reported. Worker audit pending.
- **User/fill stream: BLOCKED** — requires apiKey, secret, passphrase in .env
- **Stale mark REST fallback: LIVE** — commit b31b548
- **Dashboard redesign: COMPLETE**
