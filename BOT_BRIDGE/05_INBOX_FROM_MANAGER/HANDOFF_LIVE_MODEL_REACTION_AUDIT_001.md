# HANDOFF - LIVE_MODEL_REACTION_AUDIT_001

## Scope
Audit/verification only.
No production code changes.
No strategy redesign.
No scope widening.

## Exact active code path inspected
- `mlb_model\integration\recommendation_api.py`
- `mlb_model\integration\recommendation_schema.py`
- `mlb_model\sports\mlb\live_game_registry.py`
- `mlb_model\sports\mlb\game_state_service.py`
- `mlb_model\sports\mlb\winprob_inference.py`
- `mlb_model\sports\mlb\market_state_stream.py`
- `mlb_model\core\execution_guard.py`
- `mlb_model\data\state_snapshot_builder.py`
- `mlb_model\data\feature_store.py`
- `mlb_model\data\pregame_prior_builder.py`
- `sports_bot_v2\core\model_bridge.py`

## Top conclusion
The current model is **PARTIALLY live-reactive**, not merely static pregame, but not yet a fully trusted high-granularity live baseball model either.

## Verified live inputs that feed recommendation generation

### Inputs that can change raw fair probability via inference
From the active `GameStateSnapshot` -> `winprob_inference` path, current live inference is driven by live fields including:
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
- plus pregame prior / pregame probability input

### Inputs that can change edge/action/gating after fair probability is computed
- `ask_yes`
- `ask_no`
- `spread`
- thin-side depth
- market/book freshness (`book_age_sec`)
- game-state freshness (`game_state_age_sec`)
- live-since timing
- near-resolution checks
- data-quality score

## Practical meaning
When the game changes, the current system can recalculate more than a cosmetic live label. It can update the inferred win probability using actual in-game baseball state, then recompute edge, confidence, action candidate, and size guidance from refreshed market state and execution gating.

## Important boundary
`core\execution_guard.py` is operational gating, not the raw probability model. It can change whether a recommendation survives into an action, but it does not itself change the fair probability produced by inference.
