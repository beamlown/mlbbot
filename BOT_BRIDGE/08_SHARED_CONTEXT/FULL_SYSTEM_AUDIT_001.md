# FULL_SYSTEM_AUDIT_001

## Current architecture summary

Verified roots audited:
- `C:\Users\johnny\Desktop\BOT_BRIDGE`
- `C:\Users\johnny\Desktop\sports_bot_v2`
- `C:\Users\johnny\Desktop\mlb_model`

Verified intended authority model:
- `mlb_model` = MLB recommendation authority
- `sports_bot_v2` = execution, risk enforcement, DB truth, dashboard/API serving
- `BOT_BRIDGE` = task, handoff, review, and shared-context control plane

Verified execution chain in current code:
1. `mlb_model\integration\recommendation_api.py` produces recommendation objects using model inference, game-state fetch, market-state fetch, and gate checks.
2. `sports_bot_v2\core\model_bridge.py` reads `mlb_model\logs\shadow_recommendations.jsonl`, validates freshness/model version/market type/edge/confidence/book/game-state freshness, and emits approved intents.
3. `sports_bot_v2\bot_core.py` consumes bridge intents, constructs execution signals, calls `open_position(...)`, then persists with `insert_open_trade(...)`.
4. `sports_bot_v2\dashboard_server.py` serves the dashboard/API and reads runtime truth from `runtime\state.json`, SQLite, market stream state, and scoreboard/game data.

Important current authority truth:
- `sports_bot_v2\bot_core.py` now disables local MLB origination by default via `ALLOW_LOCAL_MLB_ORIGINATION = os.getenv("ALLOW_LOCAL_MLB_ORIGINATION", "0") == "1"`.
- The local `generate_signal(...)` MLB origination path still exists in code, but the default production path now skips it before execution.
- This is a meaningful first-step authority cleanup, not full final authority purity.
- `mlb_model\integration\recommendation_api.py` still contains execution-style operational gates (`check_all_gates`, size tiering, confidence derivation), so the final desired split is still not fully clean.

## Current runtime truth

Correct verified dashboard/API base URL:
- `http://localhost:8900`

Proof:
- `sports_bot_v2\dashboard_server.py` header says `Port: 8900`.
- `PORT = int(os.getenv("DASHBOARD_PORT", "8900"))`
- server binds with `ThreadingHTTPServer(("0.0.0.0", PORT), DashHandler)`
- `sports_bot_v2\logs\dashboard.log` repeatedly logs `MLB Dashboard running at http://localhost:8900`

Current live runtime snapshot from `sports_bot_v2\runtime\state.json`:
- `sport`: `baseball`
- `loop_count`: `4121`
- `slots.open`: `3`
- `slots.max`: `3`
- `total_trades`: `109`
- `r25`: populated with live values, not empty fallback
- three current open positions exist for:
  - `mlb-bal-cws-2026-04-08`
  - `mlb-hou-col-2026-04-08`
  - `mlb-phi-sf-2026-04-08`

Live DB truth verified directly from `sports_bot_v2\trades_sports.db`:
- unique open-slug index exists: `idx_trades_one_open_per_slug`
- duplicate open rows currently found: `0`
- current open rows: `3`

## Current verified capabilities

### 1. Bridge-based MLB execution path is active
Verified by code and logs:
- `sports_bot_v2\core\model_bridge.py` approves intents from model output.
- `sports_bot_v2\bot_core.py` bridge branch opens paper trades with source `model_bridge`.
- `sports_bot_v2\logs\bot_core_launcher.log` shows `BRIDGE GATE PASS` and `BRIDGE OPEN trade=... source=model_bridge` lines.

### 2. Local MLB origination is disabled by default
Verified in `sports_bot_v2\bot_core.py`:
- before `generate_signal(...)`, the code now checks `if not ALLOW_LOCAL_MLB_ORIGINATION: ... continue`
- this means default production opens do not originate from local MLB signal generation.

### 3. Dashboard/API runtime target is 8900, not 8000
Verified in code and logs as above.

### 4. Realtime market pricing is stream-backed
Verified in `sports_bot_v2\core\market_stream.py`:
- websocket endpoint: `wss://ws-subscriptions-clob.polymarket.com/ws/market`
- updates are pushed into `GLOBAL_STATE_HUB.update_mark(...)`
- source is labeled `polymarket_stream`

### 5. Game-state service exists and is wired on the model side
Verified in `mlb_model\sports\mlb\game_state_service.py`:
- uses ESPN summary API
- produces live game-state snapshots with inning, outs, score, pitcher state, and timing fields
- recommendation generation consumes this state in `mlb_model\integration\recommendation_api.py`

### 6. Recommendation schema/contract exists
Verified in `mlb_model\integration\recommendation_schema.py`:
- canonical recommendation object includes probabilities, edge, confidence, freshness timestamps, game-state metadata, and action

### 7. Dashboard server and runtime are actively running
Verified in:
- `sports_bot_v2\logs\dashboard.log`
- `sports_bot_v2\runtime\state.json`

### 8. Duplicate-entry protection is currently live and proven
Verified by:
- `sports_bot_v2\core\db.py` protected insert path with `BEGIN IMMEDIATE`
- live unique partial index present in SQLite
- zero current duplicate open rows
- capacity reported as `3/3` in runtime state

### 9. r25 null/error fallback is now directly proven in current code
Verified in `sports_bot_v2\dashboard_server.py` `_read_state()`:
- empty closed-trade sample returns:
  - `win_rate: None`
  - `expectancy: None`
  - `sample_size: 0`
- DB-error fallback returns:
  - null metrics
  - zero counts
  - explicit `error` field

## Current blocked items

### 1. Polymarket user/fill stream auth remains blocked
Evidence:
- system context says user/fill stream is still blocked by missing Polymarket user-stream credentials
- BOT_BRIDGE artifacts include `RUNTIME_USER_STREAM_AUTH_UNBLOCK_001` as still relevant
- no code/log proof found that user-stream credentials are now present and working

### 2. Full final authority-model separation is not complete
Evidence:
- `sports_bot_v2\bot_core.py` still contains local signal-generation logic, even though default-open path is gated off
- `mlb_model\integration\recommendation_api.py` still contains operational execution-style gating (`check_all_gates`, size tier, confidence) rather than being a pure model-decision surface

### 3. Dashboard network dependencies are intermittently degraded
Evidence from `sports_bot_v2\logs\dashboard.log`:
- repeated ESPN refresh warnings: DNS failures, TLS timeouts, read timeouts
- dashboard still runs, but external scoreboard refresh is not fully reliable

## Major changes found

### In BOT_BRIDGE
- Existing strong artifact structure is already present under:
  - `05_INBOX_FROM_MANAGER`
  - `06_OUTBOX_FROM_WORKER`
  - `07_REVIEWS`
  - `08_SHARED_CONTEXT`
- Shared-context already contains prior audit/state documents including:
  - `BOT_BRIDGE_PATH_AUDIT_001.md`
  - `RUNTIME_TARGET_TRUTH_001.md`
  - `STATE_OF_SYSTEM.md`
  - `LAST3D_AUDIT_SUMMARY.md`
  - `MISPLACED_FILES_TO_MOVE_001.md`

### In sports_bot_v2
- `bot_core.py` contains the authority-cleanup gate disabling local MLB origination by default
- `dashboard_server.py` is confirmed to be the 8900 runtime target
- `core\market_stream.py` confirms live market stream backing
- `core\db.py` confirms protected insert path plus unique open-slug index creation
- runtime state shows active bot loop and 3 open paper positions

### In mlb_model
- recommendation engine remains live and structured
- recommendation schema is explicit and bridge-consumable
- shadow log exists and contains recommendation records with timestamps, game-state age, book age, edge, confidence, and reasons

## Bottom line

The current system is operational and materially closer to the intended architecture than before, but not fully at the final authority target. The production-safe execution path is now model -> bridge -> execution bot -> dashboard/state, the correct runtime target is `http://localhost:8900`, realtime market pricing is stream-backed, duplicate-entry protection is currently proven live, and the main remaining gaps are user-stream auth, intermittent external dashboard data fetch instability, and unfinished final authority separation.
