# FILE_ORGANIZATION_AUDIT_001

## Intended roots

### 1. BOT_BRIDGE root
Intended root:
- `C:\Users\johnny\Desktop\BOT_BRIDGE`

Intended artifact/documentation structure verified as present:
- `05_INBOX_FROM_MANAGER`
- `06_OUTBOX_FROM_WORKER`
- `07_REVIEWS`
- `08_SHARED_CONTEXT`

### 2. sports_bot_v2 root
Intended root:
- `C:\Users\johnny\Desktop\sports_bot_v2`

Intended purpose:
- execution runtime
- dashboard/API server
- runtime DB/state/logs
- execution-side bridge intake

### 3. mlb_model root
Intended root:
- `C:\Users\johnny\Desktop\mlb_model`

Intended purpose:
- model-side recommendation generation
- model artifacts
- recommendation schema/integration
- model logs

## Actual roots used

### BOT_BRIDGE actual use
The desktop-level `BOT_BRIDGE` root is actively used and mostly correct.
Observed correct content includes:
- manager handoffs in `05_INBOX_FROM_MANAGER`
- worker results in `06_OUTBOX_FROM_WORKER`
- provisional reviews in `07_REVIEWS`
- shared audits/context in `08_SHARED_CONTEXT`

### sports_bot_v2 actual use
The `sports_bot_v2` repo is correctly being used for:
- `bot_core.py`
- `dashboard_server.py`
- `dashboard.html`
- `core\...`
- `runtime\state.json`
- `logs\...`
- `trades_sports.db`

### mlb_model actual use
The `mlb_model` repo is correctly being used for:
- `integration\recommendation_api.py`
- `integration\recommendation_schema.py`
- `sports\mlb\...`
- `artifacts\...`
- `logs\shadow_recommendations.jsonl`

## Misplaced files found

Misplacement confirmed:
- wrong root exists: `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE`

Misplaced files found there:
1. `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\TASK_LIVE_FEED_STATUS_POLISH_001.json`
2. `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\HANDOFF_LIVE_FEED_STATUS_POLISH_001.md`
3. `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\RESULT_LIVE_FEED_STATUS_POLISH_001.json`
4. `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\PROVISIONAL_REVIEW_LIVE_FEED_STATUS_POLISH_001.md`
5. `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\TASK_LIVE_SESSION_VERIFY_001.json`
6. `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\HANDOFF_LIVE_SESSION_VERIFY_001.md`
7. `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\RESULT_LIVE_SESSION_VERIFY_001.json`
8. `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\PROVISIONAL_REVIEW_LIVE_SESSION_VERIFY_001.md`

Count of misplaced files found:
- `8`

Why these are misplaced:
- they are BOT_BRIDGE task/result/review artifacts
- they were written into a project-local `sports_bot_v2\BOT_BRIDGE` folder instead of the intended desktop-level BOT_BRIDGE root
- this is a pathing error, not evidence that the overall folder structure should be redesigned

## Safe moves recommended

These moves are safe because the files are documentation/task artifacts, not production code, not runtime DBs, and not active live logs.

### LIVE_FEED_STATUS_POLISH_001
- current: `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\TASK_LIVE_FEED_STATUS_POLISH_001.json`
- intended: `C:\Users\johnny\Desktop\BOT_BRIDGE\05_INBOX_FROM_MANAGER\TASK_LIVE_FEED_STATUS_POLISH_001.json`

- current: `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\HANDOFF_LIVE_FEED_STATUS_POLISH_001.md`
- intended: `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\HANDOFF_LIVE_FEED_STATUS_POLISH_001.md`

- current: `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\RESULT_LIVE_FEED_STATUS_POLISH_001.json`
- intended: `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_LIVE_FEED_STATUS_POLISH_001.json`

- current: `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\PROVISIONAL_REVIEW_LIVE_FEED_STATUS_POLISH_001.md`
- intended: `C:\Users\johnny\Desktop\BOT_BRIDGE\07_REVIEWS\PROVISIONAL_REVIEW_LIVE_FEED_STATUS_POLISH_001.md`

### LIVE_SESSION_VERIFY_001
- current: `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\TASK_LIVE_SESSION_VERIFY_001.json`
- intended: `C:\Users\johnny\Desktop\BOT_BRIDGE\05_INBOX_FROM_MANAGER\TASK_LIVE_SESSION_VERIFY_001.json`

- current: `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\HANDOFF_LIVE_SESSION_VERIFY_001.md`
- intended: `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\HANDOFF_LIVE_SESSION_VERIFY_001.md`

- current: `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\RESULT_LIVE_SESSION_VERIFY_001.json`
- intended: `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_LIVE_SESSION_VERIFY_001.json`

- current: `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\PROVISIONAL_REVIEW_LIVE_SESSION_VERIFY_001.md`
- intended: `C:\Users\johnny\Desktop\BOT_BRIDGE\07_REVIEWS\PROVISIONAL_REVIEW_LIVE_SESSION_VERIFY_001.md`

## Files that should NOT be moved

Do not move these during cleanup without a separate production reason:
- `C:\Users\johnny\Desktop\sports_bot_v2\bot_core.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html`
- all `sports_bot_v2\core\...` production modules
- `C:\Users\johnny\Desktop\sports_bot_v2\trades_sports.db`
- `C:\Users\johnny\Desktop\sports_bot_v2\runtime\state.json`
- active files under `C:\Users\johnny\Desktop\sports_bot_v2\logs\...`
- all production/model source under `C:\Users\johnny\Desktop\mlb_model\...`
- archived artifacts already correctly living under `C:\Users\johnny\Desktop\BOT_BRIDGE\09_ARCHIVE\...`

## Conclusion

The structure is already mostly correct. Do not reorganize broadly. The only clearly justified organization action is moving the 8 misplaced BOT_BRIDGE artifact files out of `sports_bot_v2\BOT_BRIDGE` into the existing desktop-level BOT_BRIDGE folders.
