# REVIEW_DASH_015

Decision: APPROVED

## What passed

- **Scope**: only `dashboard.html` modified — matches allowed_files exactly. ✅
- **WIN/LOSE pill** (line 694): `const aLabel = isYes ? 'WIN' : 'LOSE';` — exact match to spec. ✅
- **6 stat boxes** (lines 750-774): Original 3 (Entry, Current, Confidence) followed by TP (green), SL (red), Size. `sizeUsd` computed via `r.qty * r.entry_px` with `shadow_position_size_usd` fallback — matches spec. Grid is `repeat(3,1fr)` so auto-wraps to 2 rows. ✅
- **Command bar W%**: `<b id="cmd-winrate">—</b>` element added at line 338 alongside P&L and Loop stats. ✅
- **Win rate binding** (line 518): `$('cmd-winrate').textContent = s?.r25?.win_rate != null ? (s.r25.win_rate * 100).toFixed(0) + '%' : '—';` wired in `renderState()`. ✅
- **Bonus**: Worker also wired `kpi-winrate` (the KPI strip element) to `r25.win_rate ?? perf.win_rate` at line 516 — correctly feeds the existing KPI with live data. Stays within allowed file. ✅
- **Rollback**: `dashboard.html` only — revertable. ✅

## What failed

- None.

## Next action

DASH_016 (trade log team names + size) can now be promoted to ACTIVE — DASH_015 is approved and dashboard.html is unlocked.
