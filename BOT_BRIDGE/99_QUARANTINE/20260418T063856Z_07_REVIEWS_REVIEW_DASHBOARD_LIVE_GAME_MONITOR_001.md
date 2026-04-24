# REVIEW_DASHBOARD_LIVE_GAME_MONITOR_001

Decision: APPROVED

## What passed
- **Scope**: `dashboard.html` + `dashboard_server.py` (tiny backend addition). ✅
- **Primary surface**: "Live Monitor" framing — position cards, accounting strip, live game status as focal content. ✅
- **WIN/LOSE explicit**: held side (WIN/LOSE + backed target) shown in card title. ✅
- **Capital clarity**: committed capital (qty×entry), live equity (qty×current), unrealized PnL shown together. ✅
- **Trade log demoted**: secondary in drawer/tab, not default active surface. ✅
- **Backend addition correct**: bankroll.capital_committed, bankroll.available_cash, bankroll.open_trade_count added from live open trades — read-only DB query, no execution logic changed. ✅
- **Truth model preserved**: main positions still from real open paper trades only. ✅

## What failed
- None.

## Next action
- DASHBOARD_LIVE_GAME_MONITOR_001 → DONE.
