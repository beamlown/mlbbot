# REVIEW_DASHBOARD_LIVE_COMMAND_CENTER_001

Decision: APPROVED

## What passed

- **Scope**: only `dashboard.html` modified. `dashboard_server.py` untouched (`dashboard_server_modified: false`). ✅
- **LIVE tab order**: game monitor → position cards → account strip — confirmed exact. ✅
- **backed_team display**: `sideText = \`${trade.backed_team} ${trade.side_label}\`` — prominent, faded team secondary. ✅

### Critical guardrail: backend owns held-side normalization ✅

The worker inspected the actual SSE `positions_mark` payload before writing any pricing JS. Fields confirmed present: `positions[].current_price`, `positions[].current_price_stale`, `positions[].unrealized_pnl_usd`, `positions[].live_equity_usd`.

Since `current_price` is present in the SSE payload, the exception clause (deriving from `bid_yes`/`bid_no`) was correctly not invoked.

- `current_price_js_line`: `const currentHeldPrice = trade.current_price;` — SSE normalized field used directly. ✅
- `frontend_bid_branching_absent: true` — no `(trade.side === 'BUY_YES' ? ... : ...)` pattern in pricing path. ✅
- `grep_confirmation.bid_yes_in_dashboard_html: false` — `bid_yes` absent from all of dashboard.html. ✅
- `grep_confirmation.bid_no_in_dashboard_html: false` — `bid_no` absent from all of dashboard.html. ✅
- `unrealized_pct_js_line`: `((currentHeldPrice - trade.entry_px) / trade.entry_px) * 100` — derived from `current_price` only. ✅

### SSE update path (clean)

`ensureStateStream() → applyStreamPositionsMark(payload) → const next = { ...p, current_price: mark.current_price } → updateLivePositionCardInPlace(next) → .pos-current-price DOM node`

Single authority chain, no branching, in-place DOM update. ✅

- **Stale badge**: sourced from SSE `current_price_stale` field — not a client-side age computation. ✅
- **Account strip**: reads `/api/state` `r25.win_rate` and `r25.expectancy`. ✅
- **Shadow absent from LIVE tab**: `shadow_absent_from_live: true`. ✅
- **In-place DOM updates**: `in_place_dom_updates: true` — no full card list re-render on SSE tick. ✅

## Not explicitly confirmed (deferred to VERIFY phase)

- No JS console errors on load
- No horizontal scroll at 390px

Acceptable deferrals — same pattern as shell phase. Both will be required checks in `DASHBOARD_REDESIGN_VERIFY_001`.

## What failed

None.

## Rollback

Revert `dashboard.html` only. Commit `2e7bfcc`. No server changes to revert.

## Next action

- DASHBOARD_LIVE_COMMAND_CENTER_001 → DONE
- DASHBOARD_POSITIONS_HISTORY_SYSTEM_001 → ACTIVE
