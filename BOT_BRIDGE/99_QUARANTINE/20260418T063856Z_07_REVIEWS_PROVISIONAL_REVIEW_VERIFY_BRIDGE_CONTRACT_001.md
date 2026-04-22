# PROVISIONAL_REVIEW_VERIFY_BRIDGE_CONTRACT_001

Decision: PROVISIONALLY_APPROVED

Final result: `PARTIAL`

## What was proven

### 1. Richer payload is present in the approved bridge intent object
Verified in `core/model_bridge.py`: the approved intent now includes the expanded field set covering identity, matchup/team semantics, model probabilities, market costs, edge fields, confidence, size metadata, optional TP/SL/recommended-size fields, reasons, game-state fields, and freshness timestamps/ages.

### 2. bot_core execution still consumes only a thin subset
Verified in the bridge branch of `bot_core.py`:
- `slug`
- `side`
- `confidence`
- `edge`
- `entry_px`

These are the fields actually read to build the execution `Signal` and open the trade.

### 3. Preserved does not yet mean execution-facing end-to-end use
The richer payload is no longer lost in `core/model_bridge.py`, but many fields are still not used by `bot_core.py` for execution handling, monitoring, or debug visibility.

Notably still preserved-but-unused:
- `tp_price`
- `sl_price`
- `recommended_size_dollars`
- `recommended_size_units`
- `held_outcome_label`
- `reasons`
- matchup/team fields
- freshness timestamps / ages

## Why the result is PARTIAL, not VERIFIED

The contract-expansion step succeeded as a transport/preservation change.
But the richer payload is not yet fully surviving into practical execution-facing use, because `bot_core.py` still ignores most of it.

So:
- **payload preservation**: yes
- **execution-facing downstream use**: only partial
- **full end-to-end verification**: not yet

## Conclusion

`VERIFY_BRIDGE_CONTRACT_001` should be marked `PARTIAL`.
The next narrow step, if desired, is to teach `bot_core.py` to carry and preserve more of the bridge payload into execution-time truth/monitoring without adding new strategy logic.
