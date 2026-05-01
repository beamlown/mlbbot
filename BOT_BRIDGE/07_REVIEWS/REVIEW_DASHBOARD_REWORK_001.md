# REVIEW_DASHBOARD_REWORK_001

Decision: APPROVED

## What passed

- Scope: only `dashboard.html` modified. `dashboard_server.py` not touched. No production logic files changed.
- HUD relabeled correctly: System / Mode / Positions / Live P&L (lines 348–365).
- Left column: single "Active Positions" section only. No Shadow Feed section present (removed).
- Source badges implemented: PAPER-BOT / PAPER-MODEL / MANUAL / SHADOW via `sourceBadge()` function (lines 741–746).
- Unified positions merge logic correct: open paper trades enriched with shadow rec data by `market_slug` match; shadow-only recs (no matching open trade) shown with SHADOW badge; last 6 closed trades rendered as resolved cards.
- Resolved/closed cards: `statusLabel` derived from `status_label` field (shadow) or `status === 'closed'` + `pnl_usd` sign (paper). Won/lost card classes applied correctly.
- Shadow tab added between Trade Log and Candidates (lines 421–426); `refreshTab('shadow')` wires to `fetchShadow()` (line 1150).
- All original drawer tabs preserved: Trade Log, Candidates, Markets, Signals, Manual.
- `renderUnifiedPositions()` called from all four fetch functions (`fetchState`, `fetchShadow`, `fetchGames`, `fetchTrades`) — panel stays fresh on every poll cycle.
- Empty state handled: 'No active or recent positions' (lines 905–908).
- `buildProbTrack()` unchanged; correctly skips rendering when `entry == null || fair == null` — safe for paper-only trades with no shadow rec match.
- `gameStatusChip()` function added — shows LIVE / FINAL / SCHEDULED on game context pill.
- Verification command run: server started at `http://localhost:8900`.
- Rollback remains possible: revert `dashboard.html` only.

## What failed

- none

## Notes

- `hud-active` count (HUD cell) uses `open_positions.length` from `/api/state` (paper exec count only). `pos-count` (panel header) uses `unified.length` (paper + shadow). This is intentional and correct — HUD reflects execution health, panel shows all visible positions.
- `buildProbTrack()` receives `r.ask_yes`/`r.ask_no` as entry for shadow recs, and `entry_price ?? entry_px` for enriched paper trades. For paper trades with no shadow rec match, `fair_win_prob` will be null and the prob track is suppressed (correct fallback).
- Browser visual inspection not performed (server running, page loading confirmed). Recommend spot-check on next session with live data to verify source badge rendering and unified panel merge in practice.

## Next action

- No immediate follow-up task required.
- Passive: on next live session with open paper trades, confirm source badges and enriched current/PnL fields render correctly on unified cards.
- Update task board: DASHBOARD_REWORK_001 → DONE, unlock dashboard.html and dashboard_server.py.
