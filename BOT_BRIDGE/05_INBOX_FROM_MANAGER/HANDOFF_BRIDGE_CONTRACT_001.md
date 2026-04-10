# HANDOFF - BRIDGE_CONTRACT_001
## Expand bridge contract to preserve richer mlb_model recommendation payload

Allowed files:
- `C:\Users\johnny\Desktop\sports_bot_v2\core\model_bridge.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\bot_core.py` only if strictly necessary for payload handling
- `C:\Users\johnny\Desktop\mlb_model\integration\recommendation_api.py`
- `C:\Users\johnny\Desktop\mlb_model\integration\recommendation_schema.py`
- BOT_BRIDGE task/result/review files

Current emitted fields from mlb_model:
- market identity: `market_slug`, `market_id`, token ids
- teams/matchup: `home_team`, `away_team`, `tracked_team`, `is_home_team`
- model probabilities: `fair_win_prob`, `p_home`, `pregame_win_prob`
- market state: `market_yes_cost`, `market_no_cost`, `ask_yes`, `ask_no`, `spread`, `thin_side_depth_usd`
- edge/confidence: `edge_yes`, `edge_no`, `confidence`
- decision metadata: `action`, `size_tier`, `size_mult`, `reasons`
- game context: inning / outs / progress / status
- freshness: feature/game/book timestamps and ages

Current consumed subset before this task:
- slug / market_id
- side
- chosen-side entry_px
- chosen-side edge
- confidence
- source

Fields previously lost/thinned:
- team/matchup fields
- tracked outcome semantics
- both-side market costs and ask prices
- both edge fields
- size tier/multiplier
- reasoning
- game-state context
- freshness timestamps/ages
- any TP/SL/recommended-size fields if present

Narrow implementation plan:
- Expand `core/model_bridge.py` intent payload to preserve the richer model payload without changing strategy logic
- Do not invent missing strategy fields; preserve them where present, otherwise pass null/absent safely
- Avoid wider executor redesign in this step

Rollback:
- Revert the payload expansion in `core/model_bridge.py`
