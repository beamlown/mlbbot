# REVIEW_DASHBOARD_POSITIONS_HISTORY_SYSTEM_001

Decision: APPROVED (with post-hoc fixes applied)

## What passed

- **Scope**: only `dashboard.html` modified. `dashboard_server.py` untouched. ✅
- **POSITIONS tab**: HTML DOM nodes added (`positions-open-count`, `positions-summary`, `positions-open-list`, `positions-closed-list`). `renderPositionsTab` populates open positions using `buildUnifiedPositionCards(open)` — same SSE `current_price` truth chain as LIVE tab. No shadow in POSITIONS. ✅
- **HISTORY tab**: HTML DOM nodes added (`history-total-count`, `history-summary`, `history-list`). `renderHistoryTab` shows closed trades with team names from slug (`SEA @ TEX` format), WIN/LOSE direction, entry/exit prices, USD size, and close reason. ✅
- **SYSTEM tab**: HTML DOM nodes added (`system-health-grid`, `system-stream-status`, `system-process-status`, `system-diagnostics-list`). `renderSystemTab` shows bridge status, loop count, open trade count, R25 sample, stream diagnostics, process topology, shadow engine summary. ✅
- **GAMES tab**: HTML DOM nodes added (`games-total-count`, `games-tab-list`). `renderGamesTab` shows full schedule sorted with open positions first. Advisory section present under class `monitor-trade-box advisory`. ✅
- **No shadow in POSITIONS, HISTORY, SYSTEM**: confirmed. ✅
- **`renderPositionsTab` uses SSE current_price**: open positions rendered via `buildUnifiedPositionCards` which reads `current_price` directly — no local price derivation. ✅
- **Wiring**: all render functions called from the correct fetch/update paths (`renderState`, `renderUnifiedPositions`, `fetchTrades`, `renderGames`, `renderShadow`). ✅

## Issues found and fixed (commit f9d7f25)

Four issues identified during review — all corrected before ratification:

1. **Duplicate function definitions**: The Phase 3 commit (`fa12342`) accidentally inserted `tradeTeams`, `renderHistoryTab`, `renderPositionsTab`, `renderGamesTab`, `renderSystemTab` each twice (~130 lines of dead code). The second definitions were the correct/complete ones. All first-occurrence duplicates removed.

2. **Advisory label wrong**: Second `renderGamesTab` had label "Advisory" instead of "Shadow Advisory — Not Executed" as required by spec. Fixed.

3. **BUY_NO P&L sign error in `renderLiveGamesFocus`**: The "Unrealized" stat box in the LIVE tab game monitor used a locally-computed formula: `(p.entry_px - currentPx) * qty` for BUY_NO — which is incorrect (gives the negative of the correct value) and violates the truth model (local price computation instead of SSE authority). Replaced with `p.unrealized_pnl_usd ?? null` (SSE-provided field). This is the same class of error as the SEA/TEX incident.

4. **`fetchSystemDiagnostics()` not wired to system tab switch**: `refreshTab('system')` called `fetchCandidates()` and `fetchState()` but not `fetchSystemDiagnostics()`, so stream health always showed "unavailable" on tab switch. Fixed.

## What failed

None — content was functionally correct once duplicates removed and issues fixed.

## Rollback

Revert `dashboard.html` to commit `fa12342` (reverts the fixes but keeps Phase 3 content) or `2e7bfcc` (reverts Phase 3 entirely). No server changes to revert.

## Next action

- `DASHBOARD_POSITIONS_HISTORY_SYSTEM_001` → DONE — commit f9d7f25 (fixes on top of fa12342)
- `DASHBOARD_PERFORMANCE_POLISH_001` → ACTIVE — worker may begin
- `dashboard.html` lock transfers to `DASHBOARD_PERFORMANCE_POLISH_001`
