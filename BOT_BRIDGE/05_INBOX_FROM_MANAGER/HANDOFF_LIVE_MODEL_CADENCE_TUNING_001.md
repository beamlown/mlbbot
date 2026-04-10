# HANDOFF - LIVE_MODEL_CADENCE_TUNING_001

## Scope executed
- narrow cadence tuning only
- no strategy redesign
- no retraining
- no new live data sources
- no changes outside the allowed files

## Exact old cadence settings
- `mlb_model\integration\recommendation_api.py`
  - `RECOMMENDATION_LOOP_SECONDS` default: `30`
- `mlb_model\sports\mlb\game_state_service.py`
  - `GAME_STATE_CACHE_TTL` default: `15`
- `mlb_model\sports\mlb\market_state_stream.py`
  - `BOOK_CACHE_TTL` default: `5`

## Exact new cadence settings
- `mlb_model\integration\recommendation_api.py`
  - `RECOMMENDATION_LOOP_SECONDS` default: `15`
- `mlb_model\sports\mlb\game_state_service.py`
  - `GAME_STATE_CACHE_TTL` default: `8`
- `mlb_model\sports\mlb\market_state_stream.py`
  - `BOOK_CACHE_TTL` remains: `5`

## Why this is the smallest safe first step
- halving the recommendation loop from `30s` to `15s` materially improves responsiveness without claiming ultra-fast live trading
- reducing game-state cache TTL from `15s` to `8s` allows fresher live baseball state to reach inference more often
- keeping book cache at `5s` avoids the sharpest increase in Polymarket/CLOB fetch churn
- no Odds API usage was increased

## Main runtime/resource risks considered
- more frequent ESPN/game-state fetches
- more frequent recommendation cycles and associated log volume
- higher chance of transient timeout churn if upstream sources are unstable
- possible loop overlap pressure if the recommendation workload grows materially

## Why the chosen change is still safe
- this first step leaves book freshness untouched
- it tightens the two coarsest parts of the current cadence rather than all three layers at once
- it preserves the same live-reactive model path, only with more timely refresh defaults
