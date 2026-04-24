# PROVISIONAL_REVIEW_REALTIME_GAME_STATE_PUSH_001

Decision: PROVISIONALLY_APPROVED

## What changed

This stage added auth-free game-state enrichment into the existing canonical realtime position path.

### Files changed
- `core/state_hub.py`
- `dashboard_server.py`

### New state_hub fields
- `game_status`
- `inning`
- `inning_half`
- `outs`
- `home_score`
- `away_score`
- `game_source_ts`
- `game_stale`
- `game_source`

### SSE payload additions
Each tracked position in `positions_mark` can now carry:
- `game_status`
- `inning`
- `inning_half`
- `outs`
- `home_score`
- `away_score`
- `game_source_ts`
- `game_stale`
- `game_source`

## Architecture check

- no new auth dependency added
- no competing game-state system created
- current market-stream pricing path untouched
- `/api/games` polling remains the source/fallback for game context

## Truthfulness check

Game fields are now present in the realtime payload path, and stale/missing values remain explicit instead of being faked.

## Conclusion

This is the correct narrow game-state push stage: server-side enrichment only, fallback preserved, no strategy or execution changes.
