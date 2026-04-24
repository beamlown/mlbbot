# HANDOFF - VERIFY_EXECUTION_CONTRACT_BIND_001
## Verify execution contract binding in live code path

Newly bound fields under verification:
- `recommended_size_dollars`
- `tp_price`, `sl_price`
- `held_outcome_label`
- `home_team`, `away_team`, `tracked_team`
- `reasons`
- freshness/game-state fields
- execution/debug identity fields

Runtime/log/DB surfaces inspected:
- `bot_core.py`
- `core/paper_exec.py`
- live DB `C:\Users\johnny\Desktop\sports_bot_v2\trades_sports.db`
- `runtime/state.json`
- recent bot logs
- current env risk caps

For this task, VERIFIED means:
1. code path proves the fields are really bound into live open handling
2. runtime evidence shows sizing/caps/accounting/duplicate protection still behave sanely
3. downstream metadata preservation is proven where observable in current DB/log surfaces
4. no hard execution/accounting regression is found
