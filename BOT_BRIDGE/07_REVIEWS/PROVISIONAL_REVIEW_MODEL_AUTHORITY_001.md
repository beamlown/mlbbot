# PROVISIONAL_REVIEW_MODEL_AUTHORITY_001

Decision: PROVISIONALLY_APPROVED

## What was wrong before

- `sports_bot_v2` still had a production local-origination path in `bot_core.py`.
- That path called `generate_signal()` from `core\signal_base.py` and could produce local `BUY_YES` / `BUY_NO` decisions.
- This violated the required authority model where `mlb_model` must be the sole MLB decision authority.

## What changed

- A narrow production-safe gate was added in `bot_core.py`:
  - `ALLOW_LOCAL_MLB_ORIGINATION = os.getenv("ALLOW_LOCAL_MLB_ORIGINATION", "0") == "1"`
- The main local trade-origination block now exits early unless that flag is explicitly enabled.
- Default behavior is now authority-safe: no local MLB trade origination in production.

## What remains functional

- Bridge/model-issued recommendation path remains intact.
- Bridge branch still:
  - reads approved intents from `core\model_bridge.py`
  - checks capacity/current open slugs
  - executes through `open_position(...)`
  - inserts through `insert_open_trade(...)`
- Execution protections were not removed.

## Exact authority cleanup achieved

The specific authority violation removed by this step is:
- **sports_bot_v2 local MLB trade origination in production mode**

This is the correct first step because it enforces authority without trying to redesign the whole architecture in one move.

## Remaining gaps after this step

- `core\signal_base.py` still exists and still contains local decision logic, but it is no longer on the default production open path.
- Bridge contract is still thinner than the desired final recommendation contract.
- `mlb_model` still appears to contain some execution-style gating that should later be separated.

## Conclusion

This step is narrow, reversible, and materially improves authority compliance without breaking the bridge execution path.
