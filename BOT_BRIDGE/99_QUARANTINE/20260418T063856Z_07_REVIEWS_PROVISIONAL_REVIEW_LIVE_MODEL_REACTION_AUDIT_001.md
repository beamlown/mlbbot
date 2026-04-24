# PROVISIONAL_REVIEW_LIVE_MODEL_REACTION_AUDIT_001

## Outcome
PARTIAL

## 1. Does the model react live during games?
**PARTIAL, but real.**

This is not just a static pregame model with cosmetic live labels.
Current code path shows the system repeatedly re-fetches live game state, rebuilds live feature inputs, reruns probability inference, then recomputes edge/action/confidence/size guidance from fresh market state and operational gates.

## 2. Exactly which in-game fields/changes drive recalculation?

### Verified fields that can change fair probability in the active inference path
From `game_state_service.py` -> `winprob_inference.py`:
- score state:
  - `home_score`
  - `away_score`
  - `score_diff`
- time/game phase state:
  - `inning`
  - `inning_half`
  - `outs`
  - `outs_elapsed`
  - `game_progress`
- base/out state:
  - `base_state`
- pitcher/bullpen state:
  - `home_pitcher_id`
  - `away_pitcher_id`
  - `home_pitch_count`
  - `away_pitch_count`
  - `home_is_bullpen`
  - `away_is_bullpen`
  - `home_tto`
  - `away_tto`
- prior context:
  - `pregame_win_prob`

### Verified fields that can change edge/action/confidence/size after inference
From `market_state_stream.py`, `execution_guard.py`, and `recommendation_api.py`:
- `ask_yes`
- `ask_no`
- `spread`
- thin-side depth
- executable cost
- `edge_yes`
- `edge_no`
- `game_state_age_sec`
- `book_age_sec`
- `data_quality`
- `live_since_sec`
- near-resolution state
- market-type/live-state gating

## 3. Exactly which important live factors are still missing?
Verified as missing or not clearly present in the active recommendation path:
- batter identity / lineup-slot live changes
- pitch-by-pitch batter context
- live runner identity/quality beyond base occupancy encoding
- defensive substitutions / fielding alignment changes
- richer roster/injury/availability live updates beyond pitcher/bullpen state
- weather/park-state live changes
- proof of much faster-than-30-second recalculation cadence

## 4. Is the current runtime cadence fast enough for live trading?
**PARTIAL only.**

Verified current cadence surfaces:
- recommendation loop default: `30s`
- game-state cache TTL: `15s`
- market/book cache TTL: `5s`

Interpretation:
- this is a real recurring live recalculation path
- but 30 seconds is still coarse for a truly high-speed live trading model

## 5. Should the current model be trusted as a true live model yet?
**Not fully yet.**

Strict conclusion:
- it is meaningfully live-reactive
- it is more than a mostly static pregame model
- but it is still only partially there as a high-confidence true live baseball model because cadence is coarse and several richer live baseball factors are still missing from the active path

## Exact file/function anchors used
- `integration/recommendation_api.py`
  - `generate_recommendation_for_game`
  - `get_recommendations`
- `sports/mlb/game_state_service.py`
  - `get_game_snapshot`
- `sports/mlb/live_game_registry.py`
  - `get_game_by_teams`
  - `get_live_since`
- `sports/mlb/winprob_inference.py`
  - `infer_for_team`
  - `build_live_feature_row`
- `sports/mlb/market_state_stream.py`
  - `get_market_state`
  - `compute_edge`
- `core/execution_guard.py`
  - `check_all_gates`
  - `check_size_tier`
  - `compute_confidence`
- `sports_bot_v2/core/model_bridge.py`
  - `get_approved_intents`
