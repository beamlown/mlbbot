# PROVISIONAL_REVIEW_REALTIME_MARKET_STREAM_DIAG_001

Decision: PROVISIONALLY_APPROVED

Final result: `VERIFIED_CAUSE_FOUND`

## Exact cause identified

The first concrete live blocker was **not** websocket auth, payload shape, or parser logic.
It was upstream of that:

- `_tracked_open_assets()` returned an empty mapping in the live runtime
- therefore the websocket had no asset IDs to subscribe to
- therefore no live Polymarket marks could enter `state_hub`
- therefore SSE positions stayed on `mark_source: poll_fallback`

## Proof points

1. Live SSE symptom showed null mark fields with `poll_fallback`
2. `_tracked_open_assets()` initially returned `{}`
3. Open trades were present, so the issue was not absence of positions
4. After refreshing discovery, the same open-position slugs resolved to real `yes_token_id` / `no_token_id` values
5. After refresh, `_tracked_open_assets()` returned non-empty tracked asset mappings

## What this means

The immediate cause is a **runtime discovery-cache state issue**.
The Stage 1 stream path cannot ingest live marks until the live dashboard server process is using the refreshed discovery cache that now includes token IDs.

## What is not yet proven

- whether parser/state_hub are perfect once live subscription begins
- whether message types arrive as expected in the current market window

Those are downstream checks. The first blocker is already identified and verified.
