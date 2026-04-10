# Provisional Review: LIVE_FEED_STATUS_POLISH_001

## Outcome
Pass, provisional.

## What changed
- Humanized top market feed status text
- Added reconnecting fallback state on stream error / missing timestamp
- Replaced raw/missing freshness placeholders with clearer wording
- Replaced blank market microstructure fields with explicit unavailable states
- Tightened stale pricing helper copy

## Before / After
- `stream stale -123s` → `Market feed stale · 2m 3s ago`
- `stream live 4s` → `Market feed live`
- `—` in best bid/ask/spread → `No bid`, `No ask`, `Unavailable`
- `Game freshness —` → `Status available, freshness unknown`
- `Market freshness —` → `Feed age unavailable`

## Risk
Low. Copy/formatting only in frontend.

## Truthfulness check
No values were fabricated. Missing or stale states are now stated more clearly.
