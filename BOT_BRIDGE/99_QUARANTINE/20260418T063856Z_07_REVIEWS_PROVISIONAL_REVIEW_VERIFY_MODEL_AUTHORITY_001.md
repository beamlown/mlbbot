# PROVISIONAL_REVIEW_VERIFY_MODEL_AUTHORITY_001

Decision: PROVISIONALLY_APPROVED

Final result: `VERIFIED`

## What was verified

### 1. Exact local gate in current code
Verified in `bot_core.py`:

```python
ALLOW_LOCAL_MLB_ORIGINATION = os.getenv("ALLOW_LOCAL_MLB_ORIGINATION", "0") == "1"
```

and in the local origination block:

```python
if not ALLOW_LOCAL_MLB_ORIGINATION:
    logger.debug(
        "LOCAL MLB ORIGINATION DISABLED slug=%s reason=model_authority_enforced",
        market.slug,
    )
    continue
```

This gates local MLB origination off before `generate_signal(...)` can run in the normal path.

### 2. Default is off
- Default env fallback is `"0"`
- Therefore local origination is disabled unless explicitly turned on

### 3. Startup path does not set the override
Inspected:
- `launch_all.py`
- `.env`
- runtime launcher logs
- bot_core launcher log

No setting for `ALLOW_LOCAL_MLB_ORIGINATION` was found in the inspected startup/config path.

### 4. Normal production startup cannot originate MLB trades locally
Because the flag defaults off and no startup/config override was found, the normal production startup path does not reach the local `generate_signal(...) -> open_position(...) -> insert_open_trade(...)` branch.

### 5. Bridge/model path remains the production entry path
The bridge branch remains intact in `bot_core.py` and still uses model-issued intents through `get_approved_intents(open_slugs)` followed by execution/open logic.

### 6. Non-MLB impact
No separate non-MLB production startup path was identified in this workspace. Active configured production sport is baseball, so no unintended non-MLB runtime regression was proven here.

## Conclusion

The authority-first change is holding for the current production startup path. Local MLB origination is disabled by default, and model/bridge-issued recommendations remain the only production entry path.
