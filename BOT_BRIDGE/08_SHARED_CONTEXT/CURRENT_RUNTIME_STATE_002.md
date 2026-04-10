# CURRENT_RUNTIME_STATE_002

## What is working right now

### 1. Correct runtime target
- correct runtime base URL: `http://localhost:8900`
- proven by:
  - `sports_bot_v2\dashboard_server.py`
  - `sports_bot_v2\logs\dashboard.log`

### 2. Dashboard server is running
Evidence:
- `sports_bot_v2\logs\dashboard.log` contains repeated startup lines:
  - `MLB Dashboard running at http://localhost:8900`

### 3. Bot runtime loop is active
Evidence from `sports_bot_v2\runtime\state.json`:
- `now`: `2026-04-08T15:45:21.205517+00:00`
- `loop_count`: `4121`
- active engine: `sports_paper_baseball`

### 4. Paper-trade runtime state is active and populated
Current runtime state reports:
- `slots.open = 3`
- `slots.max = 3`
- `total_trades = 109`
- current open positions:
  - `mlb-bal-cws-2026-04-08`
  - `mlb-hou-col-2026-04-08`
  - `mlb-phi-sf-2026-04-08`

### 5. Live DB protections are currently working
Direct SQLite proof from `C:\Users\johnny\Desktop\sports_bot_v2\trades_sports.db`:
- unique partial index exists:
  - `idx_trades_one_open_per_slug`
- duplicate open rows currently found:
  - `0`
- current open rows:
  - `3`

### 6. Bridge execution path is working
Evidence in `sports_bot_v2\logs\bot_core_launcher.log`:
- `BRIDGE GATE PASS ...`
- `BRIDGE OPEN trade=... source=model_bridge`
This proves the model-bridge execution path is actively used in runtime history.

### 7. Stream-backed market pricing path exists in current code
Evidence in `sports_bot_v2\core\market_stream.py`:
- Polymarket market websocket client is implemented
- stream updates push marks into `GLOBAL_STATE_HUB`
- source label is `polymarket_stream`

## What is partially working

### 1. Authority model
Current state:
- much improved, but not fully final

What is proven:
- local MLB origination is disabled by default in `sports_bot_v2\bot_core.py`
- bridge/model-issued recommendations are the default production open path

What is still incomplete:
- local signal generation code still exists in `sports_bot_v2`
- `mlb_model` still contains some execution-style gating logic

### 2. Dashboard external game-data refresh
Current state:
- dashboard stays up
- ESPN refresh path is intermittently failing

Evidence in `sports_bot_v2\logs\dashboard.log`:
- DNS failures
- TLS/internal SSL errors
- read timeouts

Meaning:
- the dashboard server itself is working
- external scoreboard/game-data refresh is not fully reliable at all times

### 3. Realtime dashboard/game-state path
Current state:
- code and architecture are clearly present
- current audit did not fully live-trace every SSE/UI update edge

Meaning:
- likely operational in large part
- not fully re-proven end-to-end in this audit turn

## What is blocked

### 1. User/fill stream auth
Blocked item:
- Polymarket user/fill stream remains blocked by missing user-stream credentials

Operational consequence:
- market marks can be stream-backed
- but user-level fill/account stream functionality is not proven live

### 2. Full final authority cleanup
Blocked by remaining architecture debt:
- local MLB decision logic still exists in `sports_bot_v2`
- model side still performs execution-style gate logic that should eventually be separated more cleanly

## Correct runtime target
- expected dashboard/API verification target: `http://localhost:8900`
- not `127.0.0.1:8000`

## Realtime stream status

### Market stream
- status: `working in code and intended runtime architecture`
- evidence:
  - `sports_bot_v2\core\market_stream.py`
  - system/runtime architecture notes

### User/fill stream
- status: `blocked`
- reason:
  - missing Polymarket user-stream credentials

### Game-state push
- status: `partially verified`
- evidence:
  - model-side game-state service exists and is active in recommendation generation
  - prior BOT_BRIDGE review chain says game-state push was wired into realtime path
  - this audit did not fully replay a live client-visible push verification

## Dashboard status

### Production dashboard
- status: `running`
- served by:
  - `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`
  - `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html`
- base URL:
  - `http://localhost:8900`

### Dashboard V2 shell
- status: `present but not promoted as proven production default in this audit`
- file:
  - `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_v2.html`

## Authority-model status

### What is true now
- `mlb_model` is the intended MLB recommendation authority
- `sports_bot_v2` is executing model-approved intents via bridge path
- default production MLB origination is no longer local-first

### What is not fully true yet
- `sports_bot_v2` is not fully purged of local MLB decision logic
- `mlb_model` is not yet a perfectly pure decision surface because some execution-style operational gates remain on the model side

## Bottom line

Right now the live system is running on `http://localhost:8900`, the bot loop is active, the DB truth shows 3 open positions with zero duplicate-open rows, the bridge path is active, and stream-backed market pricing code exists. The major remaining blocked items are user/fill stream auth and full final authority-model cleanup.
