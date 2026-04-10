# CLAUDE_TASK_BOARD.md — Manager Task Board
## Last updated: 2026-04-10 — Risk management pack issued (7 phases). RISK_PIPELINE_AUDIT_001 ACTIVE (read-only, no conflicts). RESOLUTION_WATCHER_BUILD_001 ACTIVE (integration/ only).

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
| RESOLUTION_WATCHER_BUILD_001 | Build integration/resolution_watcher.py — poll Polymarket for market resolution | HIGH | integration / market resolution | `integration/__init__.py`, `integration/resolution_watcher.py` | ACTIVE |
| RISK_PIPELINE_AUDIT_001 | Audit full risk pipeline end-to-end — entry, sizing, TP/SL, accounting, held-side pricing | HIGH | risk / audit | read-only | ACTIVE |

---

## QUEUED

| task_id | title | priority | subsystem | allowed_files | blocked_by |
|---------|-------|----------|-----------|---------------|------------|
| RESOLUTION_WATCHER_INTEGRATE_001 | Wire resolved_markets.json into bot_core exit loop — force-close on resolution | HIGH | risk / exit | `bot_core.py` | RESOLUTION_WATCHER_BUILD_001 |
| TP_SL_SCHEMA_NORMALIZATION_001 | Normalize TP/SL/committed/max_loss to canonical functions in core/risk.py | HIGH | risk / schema | `core/risk.py`, `core/paper_exec.py`, `core/types.py` | RISK_PIPELINE_AUDIT_001 |
| POSITION_SIZING_RULES_001 | Define and enforce per-trade sizing: formula, caps, confidence tiers, liquidity gate | HIGH | execution / sizing | `core/paper_exec.py`, `core/risk.py` | TP_SL_SCHEMA_NORMALIZATION_001 |
| EXECUTION_RISK_MONITOR_001 | Harden exit loop: empty-OB warnings, dummy-market warnings, error logging | HIGH | risk / exit | `bot_core.py`, `core/risk.py` | TP_SL_SCHEMA_NORMALIZATION_001 + RESOLUTION_WATCHER_INTEGRATE_001 |
| BANKROLL_SESSION_RULES_001 | Enforce correct bankroll/session/available-cash accounting | HIGH | accounting / bankroll | `dashboard_server.py`, `core/paper_exec.py` | POSITION_SIZING_RULES_001 + EXECUTION_RISK_MONITOR_001 |
| RISK_AND_TP_VERIFY_001 | End-to-end verification: TP/SL, sizing, held-side pricing, bankroll all agree | HIGH | risk / verification | read-only | ALL phases 1-4 |
| RISK_AND_TP_AUDIT_001 | Final risk system audit document | MEDIUM | risk / audit | `08_SHARED_CONTEXT/` only | RISK_AND_TP_VERIFY_001 |

---

## BLOCKED

| task_id | title | reason | unblocked_by |
|---------|-------|--------|--------------|
| EXIT_GAME_AWARE_001 | Game-aware exit gate (HOLD_TO_RESOLUTION) | resolution_watcher does not exist; caused 3 stuck trades in production 2026-04-10; gate reverted. Re-scope as EXIT_GAME_AWARE_002 only after RESOLUTION_WATCHER_BUILD_001 + INTEGRATE_001 both APPROVED. | RESOLUTION_WATCHER_BUILD_001 + RESOLUTION_WATCHER_INTEGRATE_001 |
| RUNTIME_USER_STREAM_AUTH_UNBLOCK_001 | Unblock Polymarket user/fill stream auth | Missing apiKey, secret, passphrase in .env — user must supply credentials | User action required |

---

## DONE

| task_id | title | outcome | allowed_files |
|---------|-------|---------|---------------|
| SL_COOLDOWN_001 | Market cooldown after stop_loss and gap_stop exits | APPROVED — stop_loss 1800s + gap_stop 3600s live as of PID 46404 restart 2026-04-10 | `bot_core.py` |
| EXIT_PARAMS_TIGHTEN_001 | Tighten exit thresholds — TP 0.40, SL 0.12, NRP 0.97, trailing 0.10/0.12 | APPROVED — .env verified, live as of PID 22180 restart 2026-04-10 | `.env` |
| BOT_DATE_GATE_DEFENSE_001 | Date gate: reject non-today slugs in local MLB origination path | APPROVED — REVIEW on file, date gate confirmed in bot_core.py | `bot_core.py` |
| DASHBOARD_LIVE_STRIP_FIXES_001 | Dashboard live strip fixes — committed tile id, bankroll MTM, feed status wording | APPROVED — commit 7b33f18 | `dashboard.html` |
| STALE_MARK_REST_FALLBACK_001 | REST polling fallback for stale marks in dashboard_server.py | APPROVED + RUNTIME VERIFIED — commit b31b548, PID 39940. mlb-cws-kc-2026-04-11 confirmed mark_source=rest_fallback on live SSE. | `dashboard_server.py` |
| DASHBOARD_REDESIGN_LIVE_SMOKE_003 | Dashboard redesign — live smoke (round 3) | CHANGES_REQUESTED → REST fallback since verified directly. Sign regression CLOSED. Smoke series DONE. | _(none — read only)_ |
| LIVE_CARD_PNL_SIGN_REGRESSION_001 | BUY_NO unrealized P&L sign fix — process restart | APPROVED — PID 35892→43288, sign verified PASS for all 3 open positions | _(none — runtime only)_ |
| DASHBOARD_REDESIGN_LIVE_SMOKE_002 | Dashboard redesign — live smoke test (round 2) | CHANGES_REQUESTED — null current_price (stale mark); shadow-feed check was false negative (criterion met). Re-smoke as SMOKE_003 after REST fallback deployed. | _(none — read only)_ |
| DASHBOARD_REDESIGN_LIVE_SMOKE_001 | Dashboard redesign — live smoke test | FAIL (sign regression) → resolved by LIVE_CARD_PNL_SIGN_REGRESSION_001. | _(none — read only)_ |
| DASHBOARD_REDESIGN_AUDIT_001 | Dashboard redesign — audit against spec, incident closure | APPROVED — DASHBOARD_REDESIGN_AUDIT_REPORT_001.md written | _(none)_ |
| DASHBOARD_REDESIGN_VERIFY_001 | Dashboard redesign — truth preservation and usability verification | APPROVED (PASS) — RESULT_DASHBOARD_REDESIGN_VERIFY_001.json | _(none)_ |
| DASHBOARD_PERFORMANCE_POLISH_001 | Dashboard redesign — performance, flicker elimination, visual polish | APPROVED — commit a19f421 | `dashboard.html` |
| DASHBOARD_POSITIONS_HISTORY_SYSTEM_001 | Dashboard redesign — secondary tabs: POSITIONS, GAMES, HISTORY, SYSTEM | APPROVED — commits fa12342 + f9d7f25 | `dashboard.html` |
| DASHBOARD_LIVE_COMMAND_CENTER_001 | Dashboard redesign — LIVE tab: game monitor, position cards, account strip | APPROVED — commit 2e7bfcc | `dashboard.html` |
| DASHBOARD_REDESIGN_SHELL_001 | Dashboard redesign — shell, layout, 5-tab nav, default LIVE view | APPROVED — commit 552686f | `dashboard.html` |
| DASHBOARD_REDESIGN_ARCH_001 | Dashboard redesign — architecture spec and payload mapping (spec only) | APPROVED — DASHBOARD_REDESIGN_SPEC_001.md written | _(none)_ |
| EXECUTION_HELD_SIDE_SEMANTICS_001 | Normalize execution-side held-contract semantics — _held_bid(), current_held_price in risk.py and paper_exec.py | APPROVED — commit 2dbb3fc | `core/risk.py`, `core/paper_exec.py` |
| BASEBALL_POSITION_SEMANTICS_INCIDENT_001 | Fix BUY_NO dashboard math — unified held-contract SSE/display | APPROVED | `dashboard_server.py`, `dashboard.html` |
| PRICE_SOURCE_SINGLE_AUTHORITY_001 | Single price-source authority audit | APPROVED | read-only audit |
| LIVE_MODEL_REACTION_REVERIFY_001 | Re-verify live model reaction cadence | PARTIAL (needs richer live window) | read-only |
| LIVE_MODEL_CADENCE_TUNING_001 | Live model reaction cadence tuning | APPROVED | `mlb_model/` |
| LIVE_MODEL_REACTION_AUDIT_001 | Live model reaction audit | APPROVED | read-only audit |
| LIVE_SESSION_VERIFY_002 | Live session end-to-end verify (round 2) | APPROVED | read-only |
| PAPER_RESET_AND_CLEAN_START_001 | Reset open paper trades, clean session start | APPROVED | DB ops only |
| LIVE_SESSION_VERIFY_001 | Live session end-to-end verify | APPROVED | read-only |
| LIVE_FEED_STATUS_POLISH_001 | Live feed status UI polish | APPROVED | `dashboard.html` |
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
| DASH_009 | Fix resolved paper trade cards — PnL, Current price, team name | APPROVED | `dashboard.html` |
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
| All files | **UNLOCKED** |

---

## System state (2026-04-09)

- Dual-process incident: RESOLVED
- Paper state: 1 open position (ARI/NYM BUY_NO — OAK/NYY and CIN/MIA closed)
- Realtime polymarket market stream: Stage 1 VERIFIED — tracking 1 asset (ARI/NYM NO token)
- Realtime game-state push: IN
- User/fill stream: BLOCKED — requires apiKey, secret, passphrase in .env
- Dashboard SSE held-contract math: **FIXED — LIVE_CARD_PNL_SIGN_REGRESSION_001 APPROVED. PID 43288 running correct formula.**
- **Execution-side held-contract semantics: RESOLVED — commit 2dbb3fc**
- Model authority: ENFORCED
- Live model cadence: IMPROVED
- **Stale mark REST fallback: LIVE — commit b31b548, PID 39940. Verified: mlb-cws-kc-2026-04-11 received mark_source=rest_fallback, stale=false on first SSE tick after restart.**
- **Dashboard redesign: COMPLETE — sign regression closed, REST fallback live. Smoke series done.**
