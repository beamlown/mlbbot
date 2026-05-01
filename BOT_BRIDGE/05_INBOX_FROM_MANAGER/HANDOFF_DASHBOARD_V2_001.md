# HANDOFF — DASHBOARD_V2_001
## Build dashboard_v2.html as a fresh game-first live monitor shell

---

## STATUS: ACTIVE

This is a from-scratch V2 build.
Do not modify the current dashboard.
Do not replace production yet.
Create `dashboard_v2.html` side-by-side.

---

## V2 information architecture

1. **Top command bar**
   - health
   - mode
   - open position count
   - quick bankroll context

2. **Primary live monitor area**
   - hybrid live baseball + active position cards
   - main above-the-fold experience

3. **Secondary live games strip/list**
   - other live games even when no position is open

4. **Accounting strip**
   - available cash
   - capital committed
   - live position equity
   - realized P/L

5. **Secondary drawers/sections**
   - shadow diagnostics
   - trade log
   - debug/history

---

## Main primary card structure

### Game block first
- matchup
- score
- inning / inning half
- outs
- balls / strikes if available
- base occupancy / runners
- pitcher if available
- live game status

### Held position block second
- exact held side / outcome
- source
- entry
- current
- committed capital
- live equity
- unrealized PnL
- TP
- SL

This must be a true hybrid monitor card, not a trade row with metadata attached.

---

## Current endpoint contract

Use these existing endpoints only:
- `/api/state`
- `/api/trades`
- `/api/games`
- `/api/mlb-shadow`

Truth model must remain:
- main live positions come from real paper trades only
- shadow stays diagnostics only
- one canonical source for main open-position counts
- no shadow-only positions in main live area
- accounting remains truthful

---

## Acceptance criteria

1. V2 is clearly a fresh build, not a patched old page
2. live game monitor is above the fold
3. trade log is secondary
4. shadow is secondary
5. active position semantics are clear
6. accounting is understandable
7. no truth regression
