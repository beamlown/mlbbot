# PROVISIONAL_REVIEW_MARKET_STREAM_LIST_MESSAGE_FIX_001

Decision: PROVISIONALLY_APPROVED

Final result: `VERIFIED`

## What changed

A narrow parser fix was applied in `core/market_stream.py` so the realtime market stream can handle both:
- single dict event payloads
- list/batch payloads of event dicts

## Before
- parser assumed dict payloads only
- runtime error: `'list' object has no attribute 'get'`
- no state_hub updates could occur from those messages

## After
- payload is normalized into iterable items
- dict items are parsed safely
- non-dict items are ignored safely
- state_hub update path is now reachable

## Runtime proof after fix

Debug endpoint showed:
- `thread_alive = true`
- `connected = true`
- `tracked_asset_count = 3`
- `last_error = null`
- `last_message_type = book`
- `parser_hit_count = 1`
- `mark_count_received = 1`
- `last_state_hub_update_slug = mlb-phi-sf-2026-04-08`

That is the exact proof that list-message parsing was the live break point and is now fixed.

## Conclusion

This task succeeded and unblocked true live mark ingress into runtime state.
