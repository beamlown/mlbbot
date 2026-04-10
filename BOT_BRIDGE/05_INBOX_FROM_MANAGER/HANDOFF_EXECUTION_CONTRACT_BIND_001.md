# HANDOFF - EXECUTION_CONTRACT_BIND_001
## Bind safe rich bridge fields into execution-facing flow

Allowed files:
- `C:\Users\johnny\Desktop\sports_bot_v2\bot_core.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\core\model_bridge.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\core\paper_exec.py` only if strictly necessary
- `C:\Users\johnny\Desktop\mlb_model\integration\recommendation_schema.py`
- BOT_BRIDGE task/result/review files

Transported-but-unused fields before this task:
- `held_outcome_label`
- matchup/team fields
- `tp_price`, `sl_price`
- `recommended_size_dollars`, `recommended_size_units`
- `reasons`
- freshness timestamps/ages
- game-status context

Exact subset bound in this task:
- into bridge execution `Signal.components`:
  - `held_outcome_label`
  - `home_team`, `away_team`, `tracked_team`
  - `tp_price`, `sl_price`
  - `recommended_size_dollars`, `recommended_size_units`
  - `reasons`
  - freshness/game-state fields
  - market identity fields for execution/debug truth
- into open-position handling in `paper_exec.py`:
  - `recommended_size_dollars` used safely when present, capped by existing max position size
  - TP/SL/held outcome/matchup/reasons/freshness incorporated into open-trade metadata (`reason_open`)

Fields intentionally still transport-only after this task:
- deeper probability fields
- both-side market-cost detail
- both-side edge detail
- any broader model-driven exit redesign
- `recommended_size_units` as a driver of sizing semantics

Rollback:
- Revert the narrow binding changes in `bot_core.py` and `core/paper_exec.py`
