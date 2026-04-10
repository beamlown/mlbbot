# FILE_LOCATION_INDEX_002

## Important files, current locations

## 1. Key production files by subsystem

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
- MLB adapters/data:
  - `C:\Users\johnny\Desktop\sports_bot_v2\sports\mlb\adapter.py`
  - `C:\Users\johnny\Desktop\sports_bot_v2\sports\mlb\live_stats.py`
  - `C:\Users\johnny\Desktop\sports_bot_v2\sports\mlb\player_stats.py`
  - `C:\Users\johnny\Desktop\sports_bot_v2\sports\mlb\sharp_odds.py`
  - `C:\Users\johnny\Desktop\sports_bot_v2\sports\mlb\signal.py`

### mlb_model, recommendation/model side
- main recommendation service:
  - `C:\Users\johnny\Desktop\mlb_model\integration\recommendation_api.py`
- canonical recommendation schema:
  - `C:\Users\johnny\Desktop\mlb_model\integration\recommendation_schema.py`
- shadow logger:
  - `C:\Users\johnny\Desktop\mlb_model\integration\shadow_mode_logger.py`
- resolution watcher:
  - `C:\Users\johnny\Desktop\mlb_model\integration\resolution_watcher.py`
- execution-style gate module:
  - `C:\Users\johnny\Desktop\mlb_model\core\execution_guard.py`
- model selfcheck:
  - `C:\Users\johnny\Desktop\mlb_model\core\selfcheck.py`
- game-state service:
  - `C:\Users\johnny\Desktop\mlb_model\sports\mlb\game_state_service.py`
- live game registry:
  - `C:\Users\johnny\Desktop\mlb_model\sports\mlb\live_game_registry.py`
- market-state stream/book fetch:
  - `C:\Users\johnny\Desktop\mlb_model\sports\mlb\market_state_stream.py`
- win-prob inference:
  - `C:\Users\johnny\Desktop\mlb_model\sports\mlb\winprob_inference.py`
- training/eval scripts:
  - `C:\Users\johnny\Desktop\mlb_model\models\...`
- model artifacts:
  - `C:\Users\johnny\Desktop\mlb_model\artifacts\...`

## 2. Key BOT_BRIDGE docs by folder

### Manager handoffs
- root folder:
  - `C:\Users\johnny\Desktop\BOT_BRIDGE\05_INBOX_FROM_MANAGER`
- notable current task docs:
  - `HANDOFF_MODEL_AUTHORITY_001.md`
  - `HANDOFF_R25_PROOF_FIX_001.md`
  - `HANDOFF_DUPLICATE_ENTRY_LIVE_REAUDIT_001.md`
  - `HANDOFF_RUNTIME_USER_STREAM_AUTH_UNBLOCK_001.md`
  - `HANDOFF_DASHBOARD_TRUTH_002.md`
  - `HANDOFF_REALTIME_DASHBOARD_ARCH_STAGE2_001.md`

### Worker results
- root folder:
  - `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER`
- notable result docs:
  - `RESULT_MODEL_AUTHORITY_001.json`
  - `RESULT_R25_PROOF_FIX_001.json`
  - `RESULT_DUPLICATE_ENTRY_LIVE_REAUDIT_001.json`
  - `RESULT_DASHBOARD_TRUTH_002.json`
  - `RESULT_REALTIME_DASHBOARD_ARCH_STAGE2_001.json`

### Reviews
- root folder:
  - `C:\Users\johnny\Desktop\BOT_BRIDGE\07_REVIEWS`
- notable review docs:
  - `PROVISIONAL_REVIEW_MODEL_AUTHORITY_001.md`
  - `PROVISIONAL_REVIEW_R25_PROOF_FIX_001.md`
  - `PROVISIONAL_REVIEW_DUPLICATE_ENTRY_LIVE_REAUDIT_001.md`

### Shared context
- root folder:
  - `C:\Users\johnny\Desktop\BOT_BRIDGE\08_SHARED_CONTEXT`
- prior context docs:
  - `BOT_BRIDGE_PATH_AUDIT_001.md`
  - `RUNTIME_TARGET_TRUTH_001.md`
  - `STATE_OF_SYSTEM.md`
  - `LAST3D_AUDIT_SUMMARY.md`
  - `MISPLACED_FILES_TO_MOVE_001.md`
- current audit docs:
  - `FULL_SYSTEM_AUDIT_001.md`
  - `TASK_STATUS_AUDIT_001.md`
  - `FILE_ORGANIZATION_AUDIT_001.md`
  - `FILE_LOCATION_INDEX_002.md`
  - `CURRENT_RUNTIME_STATE_002.md`
  - `STILL_NEEDS_DONE_002.md`
  - `SAFE_MOVES_ONLY_001.md`

## 3. Runtime file locations

### sports_bot_v2 runtime state
- runtime state:
  - `C:\Users\johnny\Desktop\sports_bot_v2\runtime\state.json`
- discovery cache:
  - `C:\Users\johnny\Desktop\sports_bot_v2\runtime\last_discovery.json`
- odds budget file:
  - `C:\Users\johnny\Desktop\sports_bot_v2\runtime\odds_budget.json`
- bot pid:
  - `C:\Users\johnny\Desktop\sports_bot_v2\runtime\bot.pid`
- launcher log:
  - `C:\Users\johnny\Desktop\sports_bot_v2\runtime\launcher.log`

### runtime DB files
- active DB:
  - `C:\Users\johnny\Desktop\sports_bot_v2\trades_sports.db`
- archive DBs in repo root:
  - `C:\Users\johnny\Desktop\sports_bot_v2\trades_sports_archive_20260404.db`
  - `C:\Users\johnny\Desktop\sports_bot_v2\trades_sports_prepatch.db`
- archived DB under BOT_BRIDGE archive:
  - `C:\Users\johnny\Desktop\BOT_BRIDGE\09_ARCHIVE\trades_sports_pre_remediation_20260405_191246.db`

## 4. Log file locations

### sports_bot_v2 logs
- root log folder:
  - `C:\Users\johnny\Desktop\sports_bot_v2\logs`
- important logs:
  - `dashboard.log`
  - `bot_core_launcher.log`
  - `shadow_engine.log`
  - `resolution_watcher.log`
  - `bot.log`
  - `dashboard_stdout.log`
  - `dashboard_stderr.log`
  - `bot_baseball_*.log`

### mlb_model logs
- root log folder:
  - `C:\Users\johnny\Desktop\mlb_model\logs`
- important logs:
  - `shadow_recommendations.jsonl`
  - `shadow_live.log`
  - `pipeline.log`
  - `resolution_watcher.log`
- archive:
  - `C:\Users\johnny\Desktop\mlb_model\logs\archive\shadow_recommendations_pre_fix_2026-04-03.jsonl`

### BOT_BRIDGE archives/logs
- archive root:
  - `C:\Users\johnny\Desktop\BOT_BRIDGE\09_ARCHIVE`
- logs root:
  - `C:\Users\johnny\Desktop\BOT_BRIDGE\10_LOGS`

## 5. Cache/discovery file locations

- discovery cache:
  - `C:\Users\johnny\Desktop\sports_bot_v2\runtime\last_discovery.json`
- orderbook snapshot cache folder:
  - `C:\Users\johnny\Desktop\sports_bot_v2\runtime\ob_snapshots`
- model-side feature data:
  - `C:\Users\johnny\Desktop\mlb_model\data\features\...`

## 6. Realtime stream file locations

### Execution-side realtime stream surfaces
- market websocket client:
  - `C:\Users\johnny\Desktop\sports_bot_v2\core\market_stream.py`
- dashboard stream/API server:
  - `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`
- runtime state feed source:
  - `C:\Users\johnny\Desktop\sports_bot_v2\runtime\state.json`

### Model-side realtime/game-state surfaces
- game-state service:
  - `C:\Users\johnny\Desktop\mlb_model\sports\mlb\game_state_service.py`
- live-game registry:
  - `C:\Users\johnny\Desktop\mlb_model\sports\mlb\live_game_registry.py`
- market-state read path:
  - `C:\Users\johnny\Desktop\mlb_model\sports\mlb\market_state_stream.py`

## 7. Misplaced BOT_BRIDGE artifact location

Wrong root currently used for some artifacts:
- `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE`

Artifacts found there:
- `TASK_LIVE_FEED_STATUS_POLISH_001.json`
- `HANDOFF_LIVE_FEED_STATUS_POLISH_001.md`
- `RESULT_LIVE_FEED_STATUS_POLISH_001.json`
- `PROVISIONAL_REVIEW_LIVE_FEED_STATUS_POLISH_001.md`
- `TASK_LIVE_SESSION_VERIFY_001.json`
- `HANDOFF_LIVE_SESSION_VERIFY_001.md`
- `RESULT_LIVE_SESSION_VERIFY_001.json`
- `PROVISIONAL_REVIEW_LIVE_SESSION_VERIFY_001.md`
