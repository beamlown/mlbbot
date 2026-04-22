# REVIEW_BRIDGE_CONTRACT_001

Decision: APPROVED

## What passed
- **Scope**: only `core/model_bridge.py` modified. ✅
- **Payload expanded**: approved intent now carries 50+ rich fields vs the previous thin 7-field subset. ✅
- **Team/matchup, held outcome, market costs, edge fields, size tier, reasons, game-state context, freshness timestamps, tp/sl preserved** in the approved intent object. ✅
- **No new strategy logic**: this is transport preservation only. ✅
- **Bot_core not required to change**: fields preserved for downstream consumption. ✅
- **Rollback**: revert core/model_bridge.py. ✅

## Notes
- VERIFY_BRIDGE_CONTRACT_001 correctly identified that fields are present in the approved intent but bot_core still only consumed a thin subset. That led to EXECUTION_CONTRACT_BIND_001.

## Next action
- BRIDGE_CONTRACT_001 → DONE.
