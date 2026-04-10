# PROVISIONAL_REVIEW_MARKET_STREAM_DEBUG_STATUS_FIX_001

Decision: PROVISIONALLY_APPROVED

Final result: `VERIFIED`

## What caused the endpoint failure

The debug endpoint itself was not failing because of exotic JSON serialization.
It failed because `debug_status()` was not actually defined on `MarketStreamClient` at runtime.

The exact bug:
- `debug_status()` was accidentally indented under `_to_float()`
- so `GLOBAL_MARKET_STREAM.debug_status()` did not exist on the live object
- the handler path crashed when trying to call it

## What changed

- `debug_status()` was moved/fixed so it is a real method on `MarketStreamClient`
- `/api/debug/market-stream` now returns stable JSON

## What the fixed debug JSON proved

The sample live response showed:
- `thread_alive = true`
- `connected = true`
- `tracked_asset_count = 3`
- subscribe payload present
- `last_open_ts` present
- `last_message_ts` present
- `last_error = "'list' object has no attribute 'get'"`
- no state_hub updates yet

That means the runtime chain is now diagnosable and the next exact break point is known:
- **messages are arriving, but parser shape handling is wrong**

## Conclusion

This task succeeded. The debug endpoint is stable now and it exposed the real downstream runtime break cleanly.
