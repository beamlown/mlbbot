# HANDOFF - REALTIME_GAME_STATE_PUSH_001
## Enrich canonical realtime position path with auth-free game-state push

Current local source of truth for live game state:
- existing server-side `/api/games` polling/update path in `dashboard_server.py`
- no new live source invented

Minimum state_hub fields added:
- `market_slug`
- `game_status`
- `inning`
- `inning_half`
- `outs`
- `home_score`
- `away_score`
- `game_source_ts`
- `game_stale`
- `game_source`

SSE payload additions:
- existing `positions_mark` remains compatible
- each tracked position can now carry:
  - `game_status`
  - `inning`
  - `inning_half`
  - `outs`
  - `home_score`
  - `away_score`
  - `game_source_ts`
  - `game_stale`
  - `game_source`

Fallback remains:
- `/api/games` polling remains intact as the source/fallback for game context
- current market-stream pricing path remains untouched
- stale/missing game fields remain explicit and honest
