# HANDOFF - PRICE_SOURCE_SINGLE_AUTHORITY_001

## Exact current_price write/override paths found

### 1. Backend stream mark writer
- file: `C:\Users\johnny\Desktop\sports_bot_v2\core\market_stream.py`
- path: websocket message -> `GLOBAL_STATE_HUB.update_mark(...)`
- writes:
  - `current_price`
  - `best_bid`
  - `best_ask`
  - `spread`
  - `source`

### 2. Backend state owner / snapshot source
- file: `C:\Users\johnny\Desktop\sports_bot_v2\core\state_hub.py`
- path: state hub stores latest mark snapshot and exposes it to dashboard server
- owner fields include:
  - `current_price`
  - `best_bid`
  - `best_ask`
  - `spread`
  - `source`
  - freshness timestamps

### 3. Backend SSE payload builder
- file: `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`
- path: positions payload for `/api/stream/state`
- uses backend mark snapshot and labels source via `mark_source`
- this is the correct backend truth surface for live card pricing

### 4. Frontend shadow-seeded open-position builder (bug source)
- file: `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html`
- function: `buildOpenPaperPositions(...)`
- prior bad path:
  - `current_price: rec?.current_price ?? null`
- this allowed shadow recommendation data to seed live paper card `current_price` before/alongside stream-backed position updates

## Root cause found
The card could briefly show the correct stream-backed number, then flip when the frontend reused shadow-enriched open-position objects that still carried `rec?.current_price`. That meant live card `current_price` was not single-authority.

## Fix applied
In `dashboard.html` `buildOpenPaperPositions(...)`:
- removed shadow as a live-card price writer
- changed:
  - `current_price: rec?.current_price ?? null`
- to:
  - `current_price: null`

## Source precedence rule after fix
1. fresh `polymarket_stream` mark from backend state/SSE is the single authority for live paper card `current_price`
2. backend fallback may apply only when stream-backed mark is missing or stale
3. shadow data may still provide context fields, but must never write/override live paper card `current_price`

## One live proof sample
Observed from live `/api/stream/state` payload:
- repeated `positions_mark` events carried stable `mark_source: polymarket_stream`
- current price stayed tied to the stream source instead of flipping to a second source

## BUY_NO / held-side note
No independent BUY_NO conversion bug was proven in this task. The primary confirmed conflict was shadow-seeded `current_price` ownership on the frontend.
