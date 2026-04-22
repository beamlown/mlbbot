# HANDOFF_BASEBALL_POSITION_SEMANTICS_INCIDENT_001

## Final status
VERIFIED_CAUSE_FOUND

## Affected trades
- `160` / `mlb-mil-bos-2026-04-08` / `BUY_YES`
- `166` / `mlb-sea-tex-2026-04-08` / `BUY_NO`

## Proven wrong semantics point
The concrete, proven live bug was in `dashboard_server.py` inside `_stream_positions_mark()`.

Before fix:
- `live_equity_usd = qty * current_price`
- `BUY_NO unrealized_pnl_usd = (entry_px - current_price) * qty`
- `BUY_YES unrealized_pnl_usd = (current_price - entry_px) * qty`

That made BUY_NO positions internally inconsistent whenever the held contract price rose: equity went up while unrealized went down.

## Minimum normalization fix applied
Inside `_stream_positions_mark()` the open-position math was normalized to one held-contract formula for both BUY_YES and BUY_NO:
- `live_equity_usd = qty * current_price`
- `unrealized_pnl_usd = (current_price - entry_px) * qty`

This is the minimum safe held-side normalization that makes dashboard/SSE current price, equity, and unrealized use the same economic truth.

## Current price source after fix
- `current_price` comes from `GLOBAL_STATE_HUB.snapshot()`
- populated by `core.market_stream.py`
- source tag: `polymarket_stream`
- tracked asset id still comes from `_tracked_open_assets()` using `BUY_YES -> yes_token_id`, `BUY_NO -> no_token_id`

## Relation to BOS YES incident
Related family of semantics bugs.
- BOS/MIL wrong-side close incident was a held-side semantic interpretation problem around which team YES/NO represented.
- SEA/TEX BUY_NO incident was a separate math-path bug in dashboard/SSE unrealized sign handling.

## TP/SL / close monitoring
- Yes, close monitoring inherited the broader semantics risk because `core.risk.check_exit()` and `core.paper_exec` still branch on raw BUY_YES/BUY_NO and assume that side already fully represents the held contract economics.
- This specific code fix corrected the live dashboard/SSE equity/unrealized truth path, not the full execution stack redesign.

## Live proof after fix
For `166` / `mlb-sea-tex-2026-04-08` / `BUY_NO`:
- runtime stream showed `current_price` about `0.51`
- with qty `113.071009`, live equity was about `$57.67`
- normalized unrealized should therefore be about `($57.67 - $50.00) = +$7.67`
- this now matches the held-contract formula instead of the old negative sign behavior
