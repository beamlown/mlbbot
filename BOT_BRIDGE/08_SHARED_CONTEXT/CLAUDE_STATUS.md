# CLAUDE_STATUS.md — Manager Status Snapshot
## Last full resync: 2026-04-05 ~11:30 UTC

---

## System State

### Launcher
- `launch_all.py` PID 29228 — singleton guard active
- 4 children running since 09:11 UTC:
  - `shadow_engine` PID 26064
  - `bot_core` PID 42956
  - `dashboard` PID 42808 (port 8900)
  - `resolution_watcher` PID 10516

### sports_bot_v2 (paper bot)
- Loop: 167+ (as of ~11:23 UTC screenshot)
- Mode: NEUTRAL
- Bridge: ENABLED (`ENABLE_MODEL_BRIDGE = True`)
- **PnL: +$30.79 realized** (fresh slate since April 5 restart)
- Open positions: 1 — LAD@WSN, BUY_NO, entry 41.3¢, confidence 64%, source=model_bridge
- DB: 2 closed trades (IDs 47–48, both mlb-sea-laa-2026-04-04, net +$30.79)
- Archive: `trades_sports_archive_20260404.db` (46 pre-incident trades)

### mlb_model shadow engine
- Running, loop 167+ alongside bot_core
- Producing today's recs (date guard filters out pre-04-05 slugs)
- resolution_watcher running — marking resolved=True on settled markets
- Discovery: 6-7 live markets per loop

### Dashboard
- Running on port 8900 (managed by launcher)
- Accessible at `http://100.82.110.11` (LAN) and `http://localhost:8900`
- Current state: shows 1 open position (LAD), 2 resolved cards still in panel (DASH_011 in progress)

---

## What Changed Since April 4 Snapshot

| Area | Old (April 4) | Current (April 5) |
|------|--------------|-------------------|
| PnL | -$6.96 | **+$30.79** |
| Open positions | 3/3 (stale duplicates) | 1 (LAD@WSN) |
| Loop count | 5 | 167+ |
| Launcher children | 3 (no dashboard, no resolution_watcher) | **4** |
| resolution_watcher | NOT running | ✅ Running |
| Model bridge | DISABLED (kill switch) | **ENABLED** |
| Dashboard | Pre-DASH_002 design | Full redesign (DASH_002–010 applied) |
| DB | 7 stale trades + incident losses | Fresh slate — 2 clean trades |
| Process hygiene | 8× launchers, 11× dashboard running | Single launcher, PID guard clean |

---

## Active Work Orders

| Task | Title | Status |
|------|-------|--------|
| DASH_011 | Remove resolved paper trades from Positions panel | ACTIVE |
| DASH_012 | Fix game status chip — LIVE shown for unstarted games | QUEUED (after DASH_011) |

---

## Deferred Issues

| Issue | Notes |
|-------|-------|
| `no_registry_match` CWS→CHW, OAK→ATH | Cosmetic — 2 games/day missed. Low priority. |
| Native signal loop — no per-intent re-fetch protection | Safe with single instance. Hardening is future work. |

---

## Previously Stale Claims (Now Corrected)

| Old claim | Correction |
|-----------|-----------|
| PnL: -$6.96 | +$30.79 (fresh slate) |
| Loop: 5 | 167+ |
| 3/3 open slots filled | 1 open (LAD) |
| resolution_watcher active, 5 pending markets | Was NOT running on April 5 until VERIFY_STABILIZE_001 fixed it |
| Bot dashboard not in launcher | Fixed by LAUNCH_002 |
| Model bridge disabled | Re-enabled by BRIDGE_ENABLE_001 |
| Dashboard: old bloated design | Replaced by DASH_002–010 |
