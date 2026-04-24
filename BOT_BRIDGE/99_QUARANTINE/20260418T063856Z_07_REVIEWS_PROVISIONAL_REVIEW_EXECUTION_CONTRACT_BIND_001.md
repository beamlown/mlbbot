# PROVISIONAL_REVIEW_EXECUTION_CONTRACT_BIND_001

Decision: PROVISIONALLY_APPROVED

## What changed

This task moved the bridge payload from preservation-only toward execution-facing use, without adding new strategy logic.

### Before
Bridge execution in `bot_core.py` effectively consumed only:
- `slug`
- `side`
- `confidence`
- `edge`
- `entry_px`

### After
Bridge execution now also binds:
- `held_outcome_label`
- `home_team`, `away_team`, `tracked_team`
- `tp_price`, `sl_price`
- `recommended_size_dollars`, `recommended_size_units`
- `reasons`
- freshness timestamps/ages
- `game_status`, `inning`, `outs`
- market identity fields

## Safe execution binding achieved

### 1. Size handling
- `core/paper_exec.py` now uses `recommended_size_dollars` when present.
- It still respects the existing hard cap via `MAX_POSITION_SIZE_USD`.
- If absent or invalid, it falls back to the existing confidence-based sizing path.

### 2. TP/SL and execution truth metadata
- `tp_price` and `sl_price` are now bound into execution-facing signal components.
- They are preserved into `reason_open` metadata for downstream truth/debug visibility.

### 3. Monitoring/debug truth
- held outcome
- matchup/team context
- reasons
- freshness timestamps/ages
- game-status context

These now flow into execution metadata instead of being ignored.

## What still remains transport-only

- `p_home`, `pregame_win_prob`
- `market_yes_cost`, `market_no_cost`
- `ask_yes`, `ask_no`
- `spread`, `thin_side_depth_usd`
- `edge_yes`, `edge_no`
- `size_tier`, `size_mult`
- `recommended_size_units` as a sizing driver
- broader model-driven exit semantics

## Scope check

- No local signal generation reopened
- No strategy redesign
- No model retraining
- No broader exit-policy redesign

## Conclusion

This is the right narrow next step. Execution no longer ignores most of the rich bridge payload, and the newly bound subset is appropriate, safe, and reversible.
