# HANDOFF: RESTART_CONFIG_HASH_VERIFY_001

## What you are doing
Read-only verification that tomorrow's clean relaunch actually loaded the updated `.env` config. This is the gate that must pass before any other worker task starts.

## Why this exists
Tonight's bot ran with stale config at every restart. The `config_hash` in `runtime/state.json` stayed `2f0dd9e0ef8a` through multiple restarts while `.env` was being edited. The live process opened trades at conf=0.43 and entry=0.01 with no effective gates. We do not trust any restart until we prove the config loaded correctly.

## Prerequisite (operator must do this before you start)
1. Kill the full stack (launch_all, bot_core, dashboard_server, resolution_watcher)
2. Delete `C:\Users\johnny\Desktop\sports_bot_v2\__pycache__\bot_core.cpython-*.pyc`
3. Relaunch via `launch_all.py`
4. Give it 2 full loop cycles (~60 seconds) before running this task

## What you are checking
- `runtime/state.json` — read immediately after relaunch, record `config_hash`
- Bot startup log — find the line that logs the loaded min_conf value
- Bot gate log — find the first `BRIDGE GATE REJECT [check_entry_gates]` entry and confirm it shows the 0.65 threshold
- No new trade opened below 0.65 confidence or below 0.22 entry price
- Exactly one bot_core process running

## What a PASS looks like
- `config_hash` is anything other than `2f0dd9e0ef8a`
- Startup log shows `min_conf=0.65`
- A confidence rejection log line shows `: 0.65` as the threshold
- No sub-threshold trade opened

## What a FAIL looks like — and what to do
- `config_hash` is still `2f0dd9e0ef8a` → STOP. Report failure. Do not run any code tasks. The old process is still alive or pyc was not cleared.
- No confidence rejections in the log after 2 loops → STOP. Report. Gate may not be wired.
- A new trade opened below 0.65 or 0.22 → STOP. Report immediately.

## Scope
- Read `runtime/state.json` and bot log only
- Do NOT edit any code
- Do NOT open any follow-on tasks
- Do NOT look at dashboard, dashboard_server.py, or mlb_model
