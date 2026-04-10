# PROVISIONAL_REVIEW_VERIFY_EXECUTION_CONTRACT_BIND_001

Decision: PROVISIONALLY_APPROVED

Final result: `PARTIAL`

## What was verified

### 1. recommended_size_dollars code path is correct
Verified in `core/paper_exec.py`:
- if `signal.components["recommended_size_dollars"]` is present, it is used
- it is still capped by `MAX_POSITION_SIZE_USD`
- if absent or invalid, execution falls back to the prior confidence-based sizing path

### 2. TP/SL and metadata binding is present in the live code path
Verified in:
- `bot_core.py` bridge execution Signal construction
- `core/paper_exec.py` open_position()

The following are now bound into execution-facing metadata:
- `tp_price`
- `sl_price`
- `held_outcome_label`
- matchup/team fields
- `reasons`
- freshness/game-state fields

### 3. No execution/accounting regression was found
Verified from runtime surfaces:
- `MAX_POSITION_SIZE_USD` still present in env
- `MAX_CONCURRENT_TRADES=3` still enforced
- runtime state still reports coherent bankroll/open/cash state
- duplicate-open protection still holds
- recent logs still show bridge-capacity enforcement behavior

## Why this is not fully VERIFIED yet

The currently inspected DB/log window did not provide a clearly post-change opened trade whose persisted `reason_open` metadata could be read back and used as live artifact proof for the new metadata bundle.

So:
- **code-path verification**: strong
- **runtime regression check**: passed
- **persisted live metadata proof**: incomplete in current observation window

## Conclusion

No hard failure was proven. The change appears safe and correct, but final status should remain `PARTIAL` until a post-change open trade is observed and its stored execution metadata is read back directly.
