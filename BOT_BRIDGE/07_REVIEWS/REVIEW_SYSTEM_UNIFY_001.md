# REVIEW_SYSTEM_UNIFY_001

Decision: APPROVED

## What passed

- **Scope**: only `dashboard.html` modified — matches allowed_files exactly. ✅
- **shadowOnly removed** (lines 793-816): `renderUnifiedPositions()` now sets `const unified = enriched` — no `shadowOnly` block, no advisory-only cards injected into the Positions panel. Shadow recs with no matching paper trade no longer appear as open positions. ✅
- **Count unification** (lines 814-816): `pos-count`, `kpi-open`, and `cmd-open` all bound to `enriched.length` inside `renderUnifiedPositions()`. All three now reflect the same number — real DB open trades. ✅
- **Note on renderState()**: `renderState()` still sets `kpi-open` and `cmd-open` from `state.open_positions` (lines 524/526) on the state poll. `renderUnifiedPositions()` runs after every fetchShadow/fetchTrades/fetchGames call and overwrites those bindings with DB truth. The overwrite is correct and will dominate at steady state. ✅
- **Live PnL fix** (lines 719-728): For `_type: 'paper'` positions with qty/entry_px/current_price all present, PnL is now `(current_price - entry_px) * qty` (BUY_YES) or `(entry_px - current_price) * qty` (BUY_NO). Falls back to `unrealized_pnl_dollars ?? pnl_usd ?? null` for shadow or unmatched positions. Correctly uses actual paper contracts, not shadow's $50 estimate. ✅
- **Shadow tab intact**: `fetchShadow()`, `renderShadow()`, `renderShadowFeed()`, `latestShadowData`, and the Shadow drawer tab all untouched. Shadow enrichment still merges into enriched paper positions. ✅
- **Rollback**: `dashboard.html` only — revertable. No server restart required (client-side only change). ✅

## What failed

- None.

## Next action

Board idle. No queued tasks. Hard-refresh browser (Ctrl+Shift+R) to pick up new dashboard.html.
