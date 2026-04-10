# CLAUDE_SOUL.md — Manager Identity & Context
## Last full resync: 2026-04-05

---

## Role
- **Claude** = MANAGER ONLY. Never writes production code. Plans, briefs, reviews.
- **Worker (OpenClaw / ChatGPT)** = WORKER ONLY. Executes briefs. Reports results.
- **User** = final approval authority. Must approve before any merge/deploy.

---

## Architecture — Four Managed Processes

`launch_all.py` (PID guard singleton) starts and watchdogs 4 children:

| Process | Entry point | Purpose |
|---------|-------------|---------|
| `shadow_engine` | `mlb_model/integration/recommendation_api.py` | Shadow-mode win-prob recs; writes `shadow_recommendations.jsonl` |
| `bot_core` | `sports_bot_v2/bot_core.py` | Paper trading loop; native signal stack + model bridge |
| `dashboard` | `sports_bot_v2/dashboard_server.py` | Web UI on port 8900; reads jsonl as read-only file feed |
| `resolution_watcher` | `mlb_model/integration/resolution_watcher.py` | Watches pending shadow markets for resolution; marks resolved=True |

**Critical separation:** `sports_bot_v2` does NOT import `mlb_model` at runtime. The only connection is:
1. Dashboard reads `mlb_model/logs/shadow_recommendations.jsonl` (read-only file)
2. `core/model_bridge.py` in `sports_bot_v2` reads the same jsonl to open paper positions when the bridge is enabled

---

## Project Map: sports_bot_v2

**Location:** `C:\Users\johnny\Desktop\sports_bot_v2`

| Path | Purpose |
|------|---------|
| `launch_all.py` | Singleton launcher + watchdog for all 4 processes |
| `bot_core.py` | Main loop (30s), native signal stack + model bridge section |
| `core/model_bridge.py` | Bridge kill switch (`ENABLE_MODEL_BRIDGE`), reads shadow recs, opens paper positions |
| `core/db.py` | SQLite DB layer (`trades_sports.db`) |
| `core/discovery.py` | Kalshi market discovery (MLB tag) |
| `core/mode.py` | Regime/mode switching |
| `core/paper_exec.py` | Paper execution (simulated fills) |
| `core/risk.py` | Guard stack |
| `core/signal_base.py` | Signal scoring (confidence calc, MIN_CONFIDENCE gate) |
| `dashboard_server.py` | HTTP dashboard server on port 8900 |
| `runtime/launcher.pid` | PID guard file for launch_all.py singleton |
| `runtime/state.json` | Live PnL, open/closed trades, loop count, guard_block |
| `logs/` | Per-process log files (shadow_engine.log, bot_core_launcher.log, dashboard.log, resolution_watcher.log) |

**Current runtime state (2026-04-05 ~11:23 UTC):**
- Launcher PID: 29228 (4 children: 26064, 42956, 42808, 10516)
- Loop: 167+
- Mode: NEUTRAL, sport=baseball
- Bridge: ENABLED (`ENABLE_MODEL_BRIDGE = True`)
- PnL: +$30.79 realized (fresh slate since April 5 restart)
- Open positions: 1 (LAD@WSN, BUY_NO, entry 41.3¢, source=model_bridge)
- DB: `trades_sports.db` — 2 closed trades (IDs 47–48, both mlb-sea-laa-2026-04-04, net +$30.79)
- Archive: `trades_sports_archive_20260404.db` — 46 trades from pre-fresh-slate sessions

---

## Project Map: mlb_model

**Location:** `C:\Users\johnny\Desktop\mlb_model`

| Path | Purpose |
|------|---------|
| `integration/recommendation_api.py` | Shadow engine: discovery → filtering → model inference → recommendations |
| `integration/shadow_mode_logger.py` | Writes actionable recs to `logs/shadow_recommendations.jsonl` |
| `integration/resolution_watcher.py` | Watches pending shadow markets for resolution |
| `models/` | Training pipeline (lgbm + logistic, calibration, evaluation, export) |
| `artifacts/winprob_model.pkl` | Active production model (LightGBM, `mlb_winprob_v1_lgbm`) |
| `artifacts/calibrator.pkl` | Active calibrator |
| `logs/shadow_recommendations.jsonl` | Actionable recs (read by dashboard + model bridge) |
| `logs/shadow_live.log` | Full shadow session log |
| `logs/resolution_watcher.log` | Market resolution tracking |

**Deployed artifacts (last pipeline run: 2026-04-03 16:21):**
- Model version: `mlb_winprob_v1_lgbm`, 22 features, LightGBM promoted
- Calibrator: active
- Holdout evaluation: PROMOTED

---

## Incident History

### April 4 Incident — Duplicate processes
- Cause: `launch_all.py` PID guard used file-based check only; `dashboard_server.py` not in managed process list
- Effect: 6× bot_core + multiple bridges running simultaneously → -$218 in bad trades (pre-fresh-slate)
- Fix: BRIDGE_FIX_001 (per-intent re-fetch cap in bridge), LAUNCH_FIX_001B (ctypes liveness check for PID guard)

### April 5 Incident — Stale process accumulation
- Discovery: 8× launch_all.py, 11× dashboard, 6× bot_core still running from before LAUNCH_FIX_001B
- Fix: Killed all 33 stale PIDs, archived 46 trades, cleared DB, deleted state.json, fresh restart
- Then: LAUNCH_002 added dashboard to managed process list
- Then: VERIFY_STABILIZE_001 added resolution_watcher + date guard in dashboard

### April 5 Kill issue
- First kill attempt (`taskkill /PID` via cmd wrapper) silently failed — bash→cmd quoting issue
- Second attempt (PowerShell `Stop-Process`) succeeded
- Lesson: Use PowerShell for Windows process control from bash

---

## Dashboard — Current Design (post DASH_002–012)

| Feature | Status |
|---------|--------|
| Single sticky command bar (logo + mode + bridge badge + stats) | ✅ DASH_004 |
| Compact position cards (no sparkline, no prob track) | ✅ DASH_002 |
| Compact games ticker (not full scoreboard) | ✅ DASH_003 |
| Server-side TP/SL per trade | ✅ DASH_006 |
| Drawer: 4 tabs (Trade Log, Shadow, Candidates, Manual) | ✅ DASH_007 |
| Bridge badge reads from /api/state | ✅ DASH_005 |
| Source column correct (PAPER-MODEL vs PAPER-BOT) | ✅ DASH_006 |
| Resolved paper card PnL/Current/team display | ✅ DASH_009 |
| Section renamed "Positions", badge counts only live | ✅ DASH_010 |
| Resolved trades removed from Positions panel | 🔄 DASH_011 (active) |
| Game status chip fix (LIVE vs SCHEDULED) | 🔄 DASH_012 (queued) |

---

## Known Active Issues

| Severity | Issue | Root cause | Task |
|----------|-------|-----------|------|
| 🔴 IN PROGRESS | Resolved paper cards still render in Positions panel | resolvedPaper included in unified array | DASH_011 |
| 🔴 IN PROGRESS | LIVE status shown for pre-game/unstarted games | gameStatusChip() ignores game_status field | DASH_012 |
| 🟡 DEFERRED | no_registry_match for CWS→CHW, OAK→ATH | recommendation_api.py abbreviation aliases | Future |
| 🟡 DEFERRED | Native signal loop has no per-intent re-fetch protection | bot_core.py native loop; safe with single instance | Future |

---

## Completed Tasks (full history)

| Task ID | Title | Outcome |
|---------|-------|---------|
| DASHBOARD_REWORK_001 | Dashboard redesign planning | APPROVED |
| LAUNCH_001 | Concurrent launcher with watchdog | APPROVED |
| LAUNCH_FIX_001B | Fix PID guard — ctypes liveness check | APPROVED |
| BRIDGE_FIX_001 | Add cap + per-open re-fetch to bridge section | APPROVED |
| PAPER_BRIDGE_002 | Persist source='model_bridge' | APPROVED |
| PAPER_BRIDGE_003 | Live gate verification | APPROVED |
| SHADOW_001 | Add shadow dollar PnL, entry/current price, TP/SL | APPROVED |
| MLB_001 | Diagnose live market discovery mismatch | APPROVED |
| MLB_002 | Fix live game abbreviation alias gaps | APPROVED |
| DASH_002 | Compact position cards | APPROVED |
| DASH_003 | Replace scoreboard with compact games ticker | APPROVED |
| DASH_004 | Merge HUD + header into single command bar | APPROVED |
| DASH_005 | Add bridge_enabled field to /api/state | APPROVED |
| DASH_006 | Fix TP/SL — compute server-side per trade | APPROVED |
| DASH_007 | Simplify drawer — remove Markets and Signals tabs | APPROVED |
| DASH_008 | Remove hardcoded TP/SL JS constants | APPROVED |
| BRIDGE_ENABLE_001 | Re-enable model bridge kill switch | APPROVED |
| LAUNCH_002 | Add dashboard_server.py to launch_all.py | APPROVED |
| VERIFY_STABILIZE_001 | Fix stale shadow ghosts — resolution_watcher + date guard | APPROVED |
| DASH_009 | Fix resolved paper trade cards — PnL, Current, team name | APPROVED |
| DASH_010 | Fix section title and badge count | APPROVED |
