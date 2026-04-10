# SYSTEM_ARCHITECTURE_STATE_FINAL_001

## 1. `mlb_model` role

Current intended role:
- baseball decision authority

Current code-backed responsibilities:
- recommendation generation
- live game-state fetch and transformation
- live probability inference
- model-side probability/edge/confidence output construction
- recommendation schema definition
- shadow logging and resolution watching

Important current files:
- `C:\Users\johnny\Desktop\mlb_model\integration\recommendation_api.py`
- `C:\Users\johnny\Desktop\mlb_model\integration\recommendation_schema.py`
- `C:\Users\johnny\Desktop\mlb_model\sports\mlb\game_state_service.py`
- `C:\Users\johnny\Desktop\mlb_model\sports\mlb\live_game_registry.py`
- `C:\Users\johnny\Desktop\mlb_model\sports\mlb\winprob_inference.py`
- `C:\Users\johnny\Desktop\mlb_model\sports\mlb\market_state_stream.py`
- `C:\Users\johnny\Desktop\mlb_model\logs\shadow_recommendations.jsonl`

Current verified live-reactive inputs in the active path:
- `home_score`
- `away_score`
- `score_diff`
- `inning`
- `inning_half`
- `outs`
- `base_state`
- `game_progress`
- `outs_elapsed`
- `home_pitcher_id`
- `away_pitcher_id`
- `home_pitch_count`
- `away_pitch_count`
- `home_is_bullpen`
- `away_is_bullpen`
- `home_tto`
- `away_tto`
- `pregame_win_prob`

Current caveat:
- `mlb_model` still contains execution-style gating logic (`check_all_gates`, size tiering, confidence derivation), so final authority purity is not complete.
- the live model is genuinely reactive, but still only partially mature as a fully trusted true live model because richer live baseball factors are still missing and cadence, while improved, is still not ultra-fast.

## 2. `sports_bot_v2` role

Current intended role:
- execution
- risk enforcement
- monitoring
- DB truth
- dashboard/API serving

Current code-backed responsibilities:
- consumes approved model bridge intents
- executes paper opens/closes
- persists trade/accounting truth in SQLite and runtime state
- enforces capacity/duplicate protections
- serves dashboard/API and SSE-style state stream
- hosts market-stream state ingestion

Important current files:
- `C:\Users\johnny\Desktop\sports_bot_v2\bot_core.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\core\model_bridge.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\core\db.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\core\risk.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\core\paper_exec.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html`

Current caveat:
- local MLB decision code still exists in `sports_bot_v2`, but the default production open path is now gated away from it.

## 3. `BOT_BRIDGE` role

Current intended role:
- task root
- handoff/history layer
- review layer
- shared-context/control plane

Current verified structure:
- `05_INBOX_FROM_MANAGER`
- `06_OUTBOX_FROM_WORKER`
- `07_REVIEWS`
- `08_SHARED_CONTEXT`

Current truth:
- the desktop-level BOT_BRIDGE root is the intended and active artifact root
- prior misplaced artifacts under `sports_bot_v2\BOT_BRIDGE` were a pathing mistake
- destination verification now proves the corrected artifacts are in the intended desktop-level BOT_BRIDGE folders and the old source folder is empty

## 4. Authority chain

Current intended authority chain:
- `mlb_model recommendation`
- `-> bridge validation`
- `-> sports_bot_v2 execution`
- `-> dashboard/state`

Current proven implementation path:
1. `mlb_model\integration\recommendation_api.py` produces recommendation objects on a recurring live loop.
2. `sports_bot_v2\core\model_bridge.py` reads `mlb_model\logs\shadow_recommendations.jsonl`, validates freshness/model version/edge/confidence/book/game-state freshness, and emits approved intents.
3. `sports_bot_v2\bot_core.py` bridge branch converts intents into execution signals, opens positions, and persists them.
4. `sports_bot_v2\dashboard_server.py` serves current truth to dashboard/API consumers.

Current authority cleanup state:
- local MLB origination in `sports_bot_v2` production path is gated off by default
- bridge-first execution is now the default production open path
- final full separation is still incomplete because dormant local decision logic remains and some operational gating still lives in `mlb_model`

## 5. Realtime architecture

### Market pricing
Current state:
- stream-backed in current code

Evidence:
- `sports_bot_v2\core\market_stream.py` subscribes to Polymarket market stream and pushes marks into `GLOBAL_STATE_HUB.update_mark(...)`
- mark source remains intended to be truthful when stream data is present

### Dashboard/SSE path
Current state:
- SSE-style stream path exists and is live

Evidence:
- `/api/stream/state` returns HTTP 200 and emits `event: positions_mark`

### Game-state push
Current state:
- wired into the realtime architecture
- only partially verified end-to-end in live observation

Evidence:
- model-side game-state service exists and is active in the recommendation path
- live session verification observed coherent live runtime/dashboard surfaces
- but no new paper trade opened and no rich over-time live progression sample was captured

## 6. Fallback paths

### Current proven runtime base
- `http://localhost:8900`

### Runtime truth sources
- `sports_bot_v2\runtime\state.json`
- `sports_bot_v2\trades_sports.db`
- `sports_bot_v2\core\market_stream.py` -> `GLOBAL_STATE_HUB`
- scoreboard/game fetch paths inside `dashboard_server.py`

### Current fallback caveats
- dashboard external scoreboard/game refresh can degrade due to DNS/TLS/timeouts
- user/fill stream remains blocked by missing credentials, so user-level stream truth is not live-proven
- paper bankroll baseline was not artificially reset after closeout; historical bankroll truth was preserved intentionally

## 7. Risk/accounting state

Current proven accounting/risk truths:
- duplicate-entry protection is live and proven
- current live DB has `0` duplicate open rows
- unique partial index exists: `idx_trades_one_open_per_slug`
- duplicate protection uses `BEGIN IMMEDIATE` and unique-index-backed open-slug protection
- after paper reset/clean start, current clean paper state has:
  - open positions = `0`
  - capital committed = `0.00`
  - history preserved
- bankroll current was intentionally not forced to a fake `$500.00` baseline because current accounting logic computes from preserved realized history

## 8. Current dashboard truth model

Current intended dashboard truth:
- production dashboard/API lives at `http://localhost:8900`
- dashboard should reflect runtime/DB/stream truth from current sports_bot_v2 execution state
- live market pricing is stream-backed
- Odds API is intended to remain verification-only and budgeted, not streamed

Current reality:
- dashboard server is running and responds on `localhost:8900`
- live session verification observed a true live MLB window
- runtime/dashboard surfaces remained coherent
- but live proof remains partial because there was no new paper trade and no strong over-time live progression delta captured in the observation window

## 9. Current blocked architecture item

### User/fill stream auth
Blocked by missing Polymarket credentials:
- `apiKey`
- `secret`
- `passphrase`

Consequence:
- market stream and SSE-style dashboard stream can be live
- user/fill/account stream remains blocked and not fully integrated in a live-proven way

## 10. Live-model cadence state

Current tuned defaults:
- recommendation loop default: `15s`
- game-state cache TTL default: `8s`
- book cache TTL default: `5s`

Interpretation:
- cadence is meaningfully tighter than before
- no instability was proven from the tighter loop
- reverify still remained partial because the observed live window did not produce enough recommendation-side progression evidence to call the faster cadence fully proven end-to-end
