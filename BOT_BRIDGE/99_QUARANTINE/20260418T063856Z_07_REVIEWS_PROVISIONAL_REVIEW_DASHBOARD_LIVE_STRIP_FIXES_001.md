# PROVISIONAL_REVIEW_DASHBOARD_LIVE_STRIP_FIXES_001

## Decision
IMPLEMENTED

## Scope compliance
- Changed only `dashboard.html`.
- No edits to `dashboard_server.py` or any other file.
- No restart required by task scope.

## What changed
1. Added `id="live-committed"` to the LIVE tab Capital Committed tile.
2. Bound `live-committed` in `renderState()` so it mirrors `cash-committed`.
3. Added module-level `_availableCash` state.
4. Stored `available_cash` from state into `_availableCash`.
5. Updated SSE handler so command-bar bankroll becomes mark-to-market: `available_cash + live_equity_total`.
6. Changed stale feed wording to `Market feed live · prices stale`.

## Static verification
- `dashboard.html` is the only changed file.
- `live-committed` exists in the LIVE tab tile.
- `_availableCash` exists at module scope and is populated in `renderState()`.
- `applyStreamPositionsMark()` now updates `kpi-bankroll` from MTM bankroll.
- Feed stale text is now `Market feed live · prices stale`.

## Runtime note
Per task rules, no process restart is required. Browser hard refresh is sufficient for runtime verification.

## Artifact paths
- Result: `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_DASHBOARD_LIVE_STRIP_FIXES_001.json`
- Review: `C:\Users\johnny\Desktop\BOT_BRIDGE\07_REVIEWS\PROVISIONAL_REVIEW_DASHBOARD_LIVE_STRIP_FIXES_001.md`
