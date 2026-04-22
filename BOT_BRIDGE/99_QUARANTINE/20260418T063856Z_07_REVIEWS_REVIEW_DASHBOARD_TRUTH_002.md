# REVIEW_DASHBOARD_TRUTH_002

Decision: APPROVED

## What passed
- **Scope**: only `dashboard.html` modified. ✅
- **Truth source**: main position cards now built from `openPaperPositions = buildOpenPaperPositions(latestTrades, ...)` where latestTrades is sourced from `/api/trades` filtered to real open paper trades only. ✅
- **Shadow demoted**: shadow-only entries excluded from main cards, remain in diagnostics only. ✅
- **PnL correct**: real qty/entry_px/current_price basis used for BUY_YES/BUY_NO. ✅
- **Stale price explicit**: card labels "Current (stale)" when current_price unavailable. ✅
- **Count ownership**: pos-count/kpi-open/cmd-open derive from openPaperPositions. ✅
- **Backend not required**: scope correctly stayed in dashboard.html only. ✅

## What failed
- None.

## Next action
- DASHBOARD_TRUTH_002 → DONE.
