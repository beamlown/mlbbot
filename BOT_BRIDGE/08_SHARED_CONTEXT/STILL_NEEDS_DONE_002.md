# STILL_NEEDS_DONE_002

## MUST FIX

### 1. Unblock Polymarket user/fill stream auth
- why it still matters: without user-stream credentials, the system cannot fully rely on realtime user/fill/account-stream truth.
- exact likely files involved:
  - `C:\Users\johnny\Desktop\sports_bot_v2\.env`
  - runtime/auth config used by the user-stream path
  - BOT_BRIDGE task chain around `RUNTIME_USER_STREAM_AUTH_UNBLOCK_001`
- do now or later: `now`

### 2. Finish final authority separation
- why it still matters: the intended architecture says `mlb_model` should be the MLB decision authority and `sports_bot_v2` should be execution/risk/monitoring only. Current code is closer, but not fully clean yet.
- exact likely files involved:
  - `C:\Users\johnny\Desktop\sports_bot_v2\bot_core.py`
  - `C:\Users\johnny\Desktop\sports_bot_v2\core\signal_base.py`
  - `C:\Users\johnny\Desktop\sports_bot_v2\core\model_bridge.py`
  - `C:\Users\johnny\Desktop\mlb_model\integration\recommendation_api.py`
  - `C:\Users\johnny\Desktop\mlb_model\core\execution_guard.py`
- do now or later: `now`, but only as a narrow architecture cleanup, not a redesign

### 3. Re-verify live dashboard truth end-to-end against served endpoints
- why it still matters: the r25 fallback behavior is now directly proven in current `dashboard_server.py`, but this audit still did not fully compare every displayed dashboard element with live API payloads and DB truth.
- exact likely files involved:
  - `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`
  - `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html`
  - `C:\Users\johnny\Desktop\sports_bot_v2\runtime\state.json`
  - `C:\Users\johnny\Desktop\sports_bot_v2\trades_sports.db`
- do now or later: `now`

## SHOULD FIX

### 4. Stabilize dashboard external data refresh reliability
- why it still matters: dashboard logs show ESPN fetch failures, TLS issues, DNS failures, and timeouts. The dashboard still runs, but external game-data refresh is intermittently degraded.
- exact likely files involved:
  - `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`
  - possibly network/DNS/environment config outside repo
  - `C:\Users\johnny\Desktop\sports_bot_v2\logs\dashboard.log`
- do now or later: `now`, if dashboard freshness matters operationally

### 5. Re-verify realtime game-state push all the way to the dashboard client
- why it still matters: the service path exists, but this audit did not fully trace a live push event from source to rendered client state.
- exact likely files involved:
  - `C:\Users\johnny\Desktop\mlb_model\sports\mlb\game_state_service.py`
  - `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`
  - any realtime/SSE path inside the dashboard server
  - `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html`
- do now or later: `later`, unless realtime UI correctness is the top priority

## NICE TO HAVE

### 7. Move the misplaced BOT_BRIDGE artifacts into the correct desktop BOT_BRIDGE folders
- why it still matters: the current structure is mostly correct, but 8 task/result/review artifacts are sitting in the wrong root and create organizational drift.
- exact likely files involved:
  - `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\TASK_LIVE_FEED_STATUS_POLISH_001.json`
  - `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\HANDOFF_LIVE_FEED_STATUS_POLISH_001.md`
  - `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\RESULT_LIVE_FEED_STATUS_POLISH_001.json`
  - `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\PROVISIONAL_REVIEW_LIVE_FEED_STATUS_POLISH_001.md`
  - `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\TASK_LIVE_SESSION_VERIFY_001.json`
  - `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\HANDOFF_LIVE_SESSION_VERIFY_001.md`
  - `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\RESULT_LIVE_SESSION_VERIFY_001.json`
  - `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE\PROVISIONAL_REVIEW_LIVE_SESSION_VERIFY_001.md`
- do now or later: `later`, after explicit move approval

### 8. Normalize BOT_BRIDGE task/result/review naming and closure discipline
- why it still matters: multiple task chains are clearly real, but later audits still have to interpret whether something is verified, partial, or superseded because closure status is not always explicit.
- exact likely files involved:
  - `C:\Users\johnny\Desktop\BOT_BRIDGE\05_INBOX_FROM_MANAGER\...`
  - `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\...`
  - `C:\Users\johnny\Desktop\BOT_BRIDGE\07_REVIEWS\...`
- do now or later: `later`

### 9. Remove or explicitly quarantine obsolete local MLB decision code after the final authority cleanup is accepted
- why it still matters: leaving dormant local-decision code around increases future regression risk.
- exact likely files involved:
  - `C:\Users\johnny\Desktop\sports_bot_v2\core\signal_base.py`
  - local MLB decision path inside `C:\Users\johnny\Desktop\sports_bot_v2\bot_core.py`
- do now or later: `later`, after explicit approval and only once replacement path is fully proven
