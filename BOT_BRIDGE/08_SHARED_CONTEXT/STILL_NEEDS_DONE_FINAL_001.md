# STILL_NEEDS_DONE_FINAL_001

## MUST FIX

### 1. Unblock Polymarket user/fill stream auth
- why it matters: without user-stream credentials, the system cannot fully rely on realtime user/fill/account-stream truth
- exact likely files involved:
  - `C:\Users\johnny\Desktop\sports_bot_v2\.env`
  - runtime/auth config for the user-stream path
  - BOT_BRIDGE task chain around `RUNTIME_USER_STREAM_AUTH_UNBLOCK_001`
- blocked or not blocked: `BLOCKED`
- recommended priority order: `1`

### 2. Finish final authority separation
- why it matters: the intended architecture says `mlb_model` should be the MLB decision authority and `sports_bot_v2` should be execution/risk/monitoring only; current code is closer, but not fully clean yet
- exact likely files involved:
  - `C:\Users\johnny\Desktop\sports_bot_v2\bot_core.py`
  - `C:\Users\johnny\Desktop\sports_bot_v2\core\signal_base.py`
  - `C:\Users\johnny\Desktop\sports_bot_v2\core\model_bridge.py`
  - `C:\Users\johnny\Desktop\mlb_model\integration\recommendation_api.py`
  - `C:\Users\johnny\Desktop\mlb_model\core\execution_guard.py`
- blocked or not blocked: `NOT_BLOCKED`
- recommended priority order: `2`

### 3. Re-verify live dashboard truth end-to-end against served endpoints
- why it matters: endpoint-level proof exists, but not every displayed dashboard element has been re-proven against live API payloads and DB truth
- exact likely files involved:
  - `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`
  - `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html`
  - `C:\Users\johnny\Desktop\sports_bot_v2\runtime\state.json`
  - `C:\Users\johnny\Desktop\sports_bot_v2\trades_sports.db`
- blocked or not blocked: `NOT_BLOCKED`
- recommended priority order: `3`

## SHOULD FIX

### 4. Re-verify realtime game-state push all the way to the dashboard client
- why it matters: the service path exists, but end-to-end live proof of client-visible in-progress card behavior is still incomplete
- exact likely files involved:
  - `C:\Users\johnny\Desktop\mlb_model\sports\mlb\game_state_service.py`
  - `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`
  - realtime/SSE path inside dashboard server
  - `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html`
- blocked or not blocked: `NOT_BLOCKED`
- recommended priority order: `4`

### 5. Continue live-model reaction verification during a richer live window
- why it matters: the model is genuinely live-reactive and cadence is now tighter, but live proof is still limited by observation windows that did not yield enough recommendation-side progression deltas
- exact likely files involved:
  - `C:\Users\johnny\Desktop\mlb_model\integration\recommendation_api.py`
  - `C:\Users\johnny\Desktop\mlb_model\sports\mlb\game_state_service.py`
  - `C:\Users\johnny\Desktop\mlb_model\sports\mlb\winprob_inference.py`
  - `C:\Users\johnny\Desktop\mlb_model\sports\mlb\market_state_stream.py`
  - BOT_BRIDGE live-model verification task chain
- blocked or not blocked: `NOT_BLOCKED`
- recommended priority order: `5`

### 6. Stabilize dashboard external data refresh reliability
- why it matters: dashboard logs show ESPN fetch failures, TLS issues, DNS failures, and timeouts
- exact likely files involved:
  - `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`
  - `C:\Users\johnny\Desktop\sports_bot_v2\logs\dashboard.log`
  - possibly external network/DNS/environment config
- blocked or not blocked: `NOT_BLOCKED`
- recommended priority order: `6`

## NICE TO HAVE

### 7. Normalize BOT_BRIDGE task/result/review naming and closure discipline
- why it matters: later audits still spend time resolving whether some tasks are verified, partial, or superseded because closure state is not always explicit
- exact likely files involved:
  - `C:\Users\johnny\Desktop\BOT_BRIDGE\05_INBOX_FROM_MANAGER\...`
  - `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\...`
  - `C:\Users\johnny\Desktop\BOT_BRIDGE\07_REVIEWS\...`
- blocked or not blocked: `NOT_BLOCKED`
- recommended priority order: `7`

### 8. Remove or quarantine obsolete local MLB decision code after authority cleanup is fully accepted
- why it matters: dormant local-decision code creates future regression risk even if the default path is now gated off
- exact likely files involved:
  - `C:\Users\johnny\Desktop\sports_bot_v2\core\signal_base.py`
  - local MLB decision path inside `C:\Users\johnny\Desktop\sports_bot_v2\bot_core.py`
- blocked or not blocked: `NOT_BLOCKED`
- recommended priority order: `8`

### 9. Keep artifact-root hygiene explicit
- why it matters: the misplaced BOT_BRIDGE artifact issue is now destination-verified, but the lesson should stay explicit so future task outputs do not drift back into repo-local roots
- exact likely files involved:
  - desktop-level BOT_BRIDGE task/result/review folders
  - any future path-writing logic or prompts that reference BOT_BRIDGE
- blocked or not blocked: `NOT_BLOCKED`
- recommended priority order: `9`
