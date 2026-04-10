# PROVISIONAL_REVIEW_REALTIME_MARKET_STREAM_TRACKING_FIX_001

Decision: PROVISIONALLY_APPROVED

## What changed

A narrow runtime recovery path was added so the market stream no longer stays subscribed to zero assets forever when open positions exist but token mapping was not ready at first.

### Files changed
- `core/market_stream.py`
- `dashboard_server.py`

## Before
- `_tracked_open_assets()` could return `{}`
- websocket subscribed to nothing
- no automatic recovery when discovery cache later became usable

## After
- when open positions exist and tracked assets are empty:
  - dashboard server triggers a safe discovery refresh
  - tracked assets are recomputed
- when tracked asset set changes:
  - market stream forces reconnect
  - new `assets_ids` subscribe payload is sent

## Proof

- prior diagnostic proved `_tracked_open_assets()` was `{}` in live runtime
- after this fix and runtime restart, `_tracked_open_assets()` returned non-empty tracked asset mappings for live open positions
- `/api/stream/state` still returns `200`
- fallback behavior remains intact

## Truthfulness check

This is a real recovery fix, not a false Stage 1 completion claim.
It removes the zero-asset deadlock, but full Stage 1 should still only be marked complete once true live stream-derived marks are observed entering state.
