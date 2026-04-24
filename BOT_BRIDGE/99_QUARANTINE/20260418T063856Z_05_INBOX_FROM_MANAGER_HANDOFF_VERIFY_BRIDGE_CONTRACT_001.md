# HANDOFF - VERIFY_BRIDGE_CONTRACT_001
## Verify expanded bridge contract survives into execution-facing flow

Expanded field set under verification:
- identity: `slug`, `market_slug`, `market_id`, `yes_token_id`, `no_token_id`
- decision: `side`, `action`, `held_outcome_label`
- teams/context: `home_team`, `away_team`, `tracked_team`, `is_home_team`
- probabilities/costs: `fair_win_prob`, `p_home`, `pregame_win_prob`, `market_yes_cost`, `market_no_cost`, `ask_yes`, `ask_no`, `spread`, `thin_side_depth_usd`
- edge/confidence/size: `entry_px`, `edge`, `edge_yes`, `edge_no`, `confidence`, `size_tier`, `size_mult`, `recommended_size_dollars`, `recommended_size_units`
- execution-facing optional fields: `tp_price`, `sl_price`
- reasoning/metadata: `reasons`, `model_version`, `data_quality`
- game/freshness: `inning`, `inning_half`, `outs`, `score_diff`, `game_progress`, `game_status`, `feature_timestamp`, `game_state_timestamp`, `book_timestamp`, `game_state_age_sec`, `book_age_sec`
- `source`

For this verification, end-to-end means:
1. prove the richer fields are really built into the approved intent object in `core/model_bridge.py`
2. trace which subset bot_core actually reads in the bridge execution branch
3. name which fields remain preserved but currently unused versus which are effectively dropped before execution handling
4. conclude strictly with VERIFIED or PARTIAL
