# PROVISIONAL_REVIEW_DISCOVERY_TOKEN_IDS_001

Decision: PROVISIONALLY_APPROVED

## What was verified before change

- `yes_token_id` and `no_token_id` were already parsed in `core/discovery.py` inside `_parse_market(...)`
- `core/types.py` already had fields for those token IDs on the `Market` dataclass
- the drop happened only in the reduced cache serializer that writes `runtime/last_discovery.json`

## What changed

A single narrow serializer block in `core/discovery.py` was extended to persist:
- `yes_token_id`
- `no_token_id`

No other discovery behavior was changed.

## Before/after cache shape

### Before
- `market_id`
- `slug`
- `question`
- `yes_price`
- `no_price`
- `end_iso`
- `active`
- `closed`
- `resolved`

### After
- all previous fields
- plus:
  - `yes_token_id`
  - `no_token_id`

## Proof

After a refreshed discovery run, `runtime/last_discovery.json` field list now includes both token ID fields.

## Conclusion

This cleanly removes the blocker for realtime market-stream subscription mapping without widening scope.
