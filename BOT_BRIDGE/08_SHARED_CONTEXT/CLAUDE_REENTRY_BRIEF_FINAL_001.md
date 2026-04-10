# CLAUDE_REENTRY_BRIEF_FINAL_001

## Executive summary

While Claude was away, the system moved materially closer to the intended architecture, but it is still not fully at the final target.

Current intended architecture remains:
- `mlb_model` = baseball decision authority
- `sports_bot_v2` = execution, risk enforcement, monitoring, dashboard/API truth
- `BOT_BRIDGE` = task, handoff, review, and shared-context control plane

Current intended chain remains:
- `mlb_model recommendation`
- `-> bridge validation`
- `-> sports_bot_v2 execution`
- `-> dashboard/state`

Current verified runtime target:
- `http://localhost:8900`

## What changed while Claude was down

1. **Model authority cleanup advanced**
- `sports_bot_v2\bot_core.py` gates off local MLB origination by default via `ALLOW_LOCAL_MLB_ORIGINATION`.
- Bridge/model-issued recommendations remain the default production open path.

2. **Bridge execution path is active and proven in runtime history**
- `sports_bot_v2\core\model_bridge.py` consumes filtered model recommendations from `mlb_model\logs\shadow_recommendations.jsonl`.
- Bot logs show `BRIDGE GATE PASS` and `BRIDGE OPEN ... source=model_bridge`.

3. **Duplicate-entry protection was re-audited live and is currently proven**
- Live DB path: `C:\Users\johnny\Desktop\sports_bot_v2\trades_sports.db`
- Unique partial index exists: `idx_trades_one_open_per_slug`
- Current duplicate open-row count: `0`

4. **Artifact/path audit and correction is now fully reflected**
- misplaced BOT_BRIDGE artifacts were identified under `sports_bot_v2\BOT_BRIDGE`
- later destination verification proved the relevant artifacts are now present in the correct desktop-level BOT_BRIDGE folders
- source folder `C:\Users\johnny\Desktop\sports_bot_v2\BOT_BRIDGE` is empty

5. **Paper reset / clean start was completed safely**
- all currently open paper trades were closed
- open positions were reduced to `0`
- capital committed was reduced to `0.00`
- full trade history and historical bankroll truth were preserved
- an exact fresh `$500.00` bankroll reset was intentionally **not** done because that would have conflicted with preserved realized-history truth under current accounting logic

6. **Live session verification improved but remains partial**
- `LIVE_SESSION_VERIFY_002` observed a true live MLB window
- runtime/dashboard surfaces were coherent
- but no new paper trade opened and no meaningful over-time live position progression was captured
- therefore `LIVE_SESSION_VERIFY_002` remains `PARTIAL`

7. **Live model reaction was audited more precisely**
- `LIVE_MODEL_REACTION_AUDIT_001` shows the current model is genuinely live-reactive, not just static pregame with cosmetic labels
- but it is still only `PARTIAL` as a fully trusted true live model
- verified live probability-driving fields include score, inning, half, outs, base state, game progress, pitcher IDs/pitch counts, bullpen flags, TTO, and pregame prior

8. **Live model cadence was tightened safely**
- recommendation loop default: `30s -> 15s`
- game-state cache TTL: `15s -> 8s`
- book cache TTL remains: `5s`
- no strategy redesign, retraining, or new data source was introduced

9. **Cadence reverify did not over-close the case**
- `LIVE_MODEL_REACTION_REVERIFY_001` remains `PARTIAL`
- tighter cadence is proven in code
- no instability was found
- but the available live window still did not provide enough recommendation-side progression evidence to mark the result `VERIFIED`

## What is now verified

- runtime target is `http://localhost:8900`
- dashboard server is running
- bot runtime loop is active
- bridge/model-issued trade execution path is active in runtime history
- local MLB origination is disabled by default in production path
- duplicate-entry protection is currently proven live
- unique open-slug DB index exists live
- duplicate open rows currently = `0`
- market stream code is implemented and wired into state hub
- recommendation schema/contract exists in `mlb_model`
- r25 null/error fallback is directly proven in current `dashboard_server.py`
- artifact destination state is verified and the old misplaced source folder is empty
- paper closeout/reset-safe state is verified: open positions `0`, committed capital `0.00`, history preserved
- cadence tightening in `mlb_model` is real in code: `30 -> 15`, `15 -> 8`, `5 -> 5`

## What is still partial or blocked

### Partial
- full final authority separation is not complete
- realtime game-state push is only partially verified end-to-end
- live session verification remains partial because no new live paper position opened and no strong over-time progression delta was captured
- live model is genuinely reactive but still only partial as a fully trusted true live model
- cadence reverify remains partial because the observed live window did not show enough recommendation-side progression to prove a materially stronger reaction end-to-end
- dashboard truth chain is improved, but not fully re-verified against every live UI path

### Blocked
- Polymarket user/fill stream remains blocked by missing:
  - `apiKey`
  - `secret`
  - `passphrase`

## Current top priorities

1. Unblock Polymarket user/fill stream auth.
2. Finish final authority separation without redesigning strategy.
3. Re-verify live dashboard truth end-to-end against served endpoints.
4. Re-verify realtime game-state push all the way to the dashboard client.
5. Continue live-model reaction verification during a richer live window before calling it a fully trusted true live model.

## Claude re-entry bottom line

Claude should assume the system is running, the runtime target is `http://localhost:8900`, bridge-first MLB execution is now the default production path, duplicate-entry protection is currently proven, the artifact root correction is now destination-verified, paper state is currently clean with zero open positions, the live model is genuinely reactive but only partially mature as a true live model, cadence has been tightened safely, and user-stream auth is still blocked by missing credentials.
