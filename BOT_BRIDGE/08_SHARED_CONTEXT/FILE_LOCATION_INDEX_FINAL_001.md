# FILE_LOCATION_INDEX_FINAL_001

## 1. Important production files by subsystem

### sports_bot_v2, execution/runtime/dashboard
- main execution loop:
  - `C:\Users\johnny\Desktop\sports_bot_v2\bot_core.py`
- launcher:
  - `C:\Users\johnny\Desktop\sports_bot_v2\launch_all.py`
- dashboard HTML:
  - `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html`
- alternate dashboard shell:
  - `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_v2.html`
- dashboard server/API:
  - `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`
- DB helpers:
  - `C:\Users\johnny\Desktop\sports_bot_v2\core\db.py`
- model bridge intake:
  - `C:\Users\johnny\Desktop\sports_bot_v2\core\model_bridge.py`
- market stream client:
  - `C:\Users\johnny\Desktop\sports_bot_v2\core\market_stream.py`
- state hub:
  - `C:\Users\johnny\Desktop\sports_bot_v2\core\state_hub.py`
- discovery:
  - `C:\Users\johnny\Desktop\sports_bot_v2\core\discovery.py`
- paper execution:
  - `C:\Users\johnny\Desktop\sports_bot_v2\core\paper_exec.py`
- risk gates:
  - `C:\Users\johnny\Desktop\sports_bot_v2\core\risk.py`
- local signal logic still present:
  - `C:\Users\johnny\Desktop\sports_bot_v2\core\signal_base.py`
- accounting/runtime truth surfaces:
  - `C:\Users\johnny\Desktop\sports_bot_v2\runtime\state.json`
  - `C:\Users\johnny\Desktop\sports_bot_v2\trades_sports.db`

### mlb_model, recommendation/model side
- main recommendation service:
  - `C:\Users\johnny\Desktop\mlb_model\integration\recommendation_api.py`
- recommendation schema:
  - `C:\Users\johnny\Desktop\mlb_model\integration\recommendation_schema.py`
- live registry:
  - `C:\Users\johnny\Desktop\mlb_model\sports\mlb\live_game_registry.py`
- game-state service:
  - `C:\Users\johnny\Desktop\mlb_model\sports\mlb\game_state_service.py`
- live win-prob inference:
  - `C:\Users\johnny\Desktop\mlb_model\sports\mlb\winprob_inference.py`
- market-state read path:
  - `C:\Users\johnny\Desktop\mlb_model\sports\mlb\market_state_stream.py`
- execution-style gate module:
  - `C:\Users\johnny\Desktop\mlb_model\core\execution_guard.py`
- shadow logger:
  - `C:\Users\johnny\Desktop\mlb_model\integration\shadow_mode_logger.py`
- resolution watcher:
  - `C:\Users\johnny\Desktop\mlb_model\integration\resolution_watcher.py`
- model artifacts:
  - `C:\Users\johnny\Desktop\mlb_model\artifacts\...`

## 2. BOT_BRIDGE folders and what belongs in each

### `C:\Users\johnny\Desktop\BOT_BRIDGE\05_INBOX_FROM_MANAGER`
Belongs here:
- manager task/handoff instructions
- task JSONs
- inbound work briefs

### `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER`
Belongs here:
- worker result JSONs
- worker handoff notes
- verification outputs

### `C:\Users\johnny\Desktop\BOT_BRIDGE\07_REVIEWS`
Belongs here:
- provisional reviews
- audit reviews
- verification review notes

### `C:\Users\johnny\Desktop\BOT_BRIDGE\08_SHARED_CONTEXT`
Belongs here:
- system audits
- architecture briefs
- catch-up docs
- re-entry packages
- file/location indexes

## 3. Runtime file locations

### sports_bot_v2 runtime
- state file:
  - `C:\Users\johnny\Desktop\sports_bot_v2\runtime\state.json`
- discovery cache:
  - `C:\Users\johnny\Desktop\sports_bot_v2\runtime\last_discovery.json`
- odds budget:
  - `C:\Users\johnny\Desktop\sports_bot_v2\runtime\odds_budget.json`
- bot pid:
  - `C:\Users\johnny\Desktop\sports_bot_v2\runtime\bot.pid`
- launcher log:
  - `C:\Users\johnny\Desktop\sports_bot_v2\runtime\launcher.log`

### runtime DB locations
- active DB:
  - `C:\Users\johnny\Desktop\sports_bot_v2\trades_sports.db`
- repo archive DBs:
  - `C:\Users\johnny\Desktop\sports_bot_v2\trades_sports_archive_20260404.db`
  - `C:\Users\johnny\Desktop\sports_bot_v2\trades_sports_prepatch.db`
- archive DB under BOT_BRIDGE:
  - `C:\Users\johnny\Desktop\BOT_BRIDGE\09_ARCHIVE\trades_sports_pre_remediation_20260405_191246.db`

## 4. Log file locations

### sports_bot_v2 logs
- `C:\Users\johnny\Desktop\sports_bot_v2\logs\dashboard.log`
- `C:\Users\johnny\Desktop\sports_bot_v2\logs\bot_core_launcher.log`
- `C:\Users\johnny\Desktop\sports_bot_v2\logs\shadow_engine.log`
- `C:\Users\johnny\Desktop\sports_bot_v2\logs\resolution_watcher.log`
- `C:\Users\johnny\Desktop\sports_bot_v2\logs\bot.log`
- `C:\Users\johnny\Desktop\sports_bot_v2\logs\dashboard_stdout.log`
- `C:\Users\johnny\Desktop\sports_bot_v2\logs\dashboard_stderr.log`

### mlb_model logs
- `C:\Users\johnny\Desktop\mlb_model\logs\shadow_recommendations.jsonl`
- `C:\Users\johnny\Desktop\mlb_model\logs\shadow_live.log`
- `C:\Users\johnny\Desktop\mlb_model\logs\pipeline.log`
- `C:\Users\johnny\Desktop\mlb_model\logs\resolution_watcher.log`

## 5. Discovery/cache file locations

- sports_bot discovery cache:
  - `C:\Users\johnny\Desktop\sports_bot_v2\runtime\last_discovery.json`
- sports_bot orderbook snapshot cache:
  - `C:\Users\johnny\Desktop\sports_bot_v2\runtime\ob_snapshots\...`
- model feature/training data:
  - `C:\Users\johnny\Desktop\mlb_model\data\features\...`

## 6. Realtime stream file locations

### market stream
- `C:\Users\johnny\Desktop\sports_bot_v2\core\market_stream.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\core\state_hub.py`

### SSE/dashboard stream
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`
- endpoint proved live: `http://localhost:8900/api/stream/state`

### game-state push surfaces
- `C:\Users\johnny\Desktop\mlb_model\sports\mlb\game_state_service.py`
- `C:\Users\johnny\Desktop\mlb_model\sports\mlb\live_game_registry.py`
- `C:\Users\johnny\Desktop\mlb_model\sports\mlb\winprob_inference.py`
- downstream dashboard/runtime consumers in `sports_bot_v2`

## 7. Dashboard files

- production dashboard:
  - `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html`
- alternate dashboard shell:
  - `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_v2.html`
- dashboard server/API:
  - `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`

## 8. Bridge/authority files

- bridge intake:
  - `C:\Users\johnny\Desktop\sports_bot_v2\core\model_bridge.py`
- authority cleanup file:
  - `C:\Users\johnny\Desktop\sports_bot_v2\bot_core.py`
- model recommendation contract:
  - `C:\Users\johnny\Desktop\mlb_model\integration\recommendation_schema.py`
- model recommendation producer:
  - `C:\Users\johnny\Desktop\mlb_model\integration\recommendation_api.py`
- model shadow log source for bridge:
  - `C:\Users\johnny\Desktop\mlb_model\logs\shadow_recommendations.jsonl`

## 9. Risk/accounting files

- DB insert/open-slug protection:
  - `C:\Users\johnny\Desktop\sports_bot_v2\core\db.py`
- risk gates:
  - `C:\Users\johnny\Desktop\sports_bot_v2\core\risk.py`
- paper execution:
  - `C:\Users\johnny\Desktop\sports_bot_v2\core\paper_exec.py`
- runtime accounting/state:
  - `C:\Users\johnny\Desktop\sports_bot_v2\runtime\state.json`
- live DB truth:
  - `C:\Users\johnny\Desktop\sports_bot_v2\trades_sports.db`

## 10. Current organization note

- do not reorganize production roots in this re-entry package
- desktop-level `BOT_BRIDGE` is the intended artifact root
- prior misplaced BOT_BRIDGE artifacts were destination-verified into the correct desktop-level BOT_BRIDGE folders
- `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE` is now empty
