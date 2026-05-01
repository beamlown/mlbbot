# PROVISIONAL_REVIEW_REALTIME_DASHBOARD_ARCH_STAGE2_001

Decision: PROVISIONALLY_APPROVED

## What changed

A minimal realtime Stage 2 slice was added without removing polling.

### Server side
- Added canonical helper: `_stream_positions_mark()`
- Added SSE route: `GET /api/stream/state`
- Route emits `positions_mark` events containing open-position held-side current price marks plus derived unrealized PnL and live equity

### Frontend side
- Added `ensureStateStream()` EventSource hookup
- Added `applyStreamPositionsMark(payload)` to patch currently rendered open positions
- Stream updates:
  - held-side current price
  - per-position unrealized PnL
  - aggregate live equity
  - freshness/staleness status text

## What did not change

- polling remains intact
- no model logic changed
- no execution logic changed
- no credentials/auth exposed client-side

## Why this satisfies Stage 2

- dashboard is no longer polling-only for at least one live metric path
- one visible live metric path is now server-pushed
- fallback remains untouched and safe
- freshness/staleness is surfaced honestly
- rollout is reversible

## Remaining later work (not part of this stage)

- longer-lived state hub abstraction if needed
- additional pushed metric families
- broader push coverage beyond the held-price/equity/PnL slice
