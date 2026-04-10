# REVIEW_MODEL_AUTHORITY_001

Decision: APPROVED

## What passed
- **Scope**: only `bot_core.py` modified. ✅
- **Authority enforced**: ALLOW_LOCAL_MLB_ORIGINATION=0 by default — local signal_base path cannot reach generate_signal/open_position/insert_open_trade in production. ✅
- **Env flag rollback**: set ALLOW_LOCAL_MLB_ORIGINATION=1 to restore local path if needed. ✅
- **Bridge path intact**: get_approved_intents() bridge branch still works; model-issued recommendations remain the only production open path. ✅
- **Execution protections preserved**: MAX_CONCURRENT_TRADES, duplicate protection, market lookup unchanged. ✅
- **Not a strategy redesign**: only a gating change. ✅

## What failed
- None.

## Notes
- First step of model authority separation. Bridge contract expansion followed as BRIDGE_CONTRACT_001.

## Next action
- MODEL_AUTHORITY_001 → DONE.
