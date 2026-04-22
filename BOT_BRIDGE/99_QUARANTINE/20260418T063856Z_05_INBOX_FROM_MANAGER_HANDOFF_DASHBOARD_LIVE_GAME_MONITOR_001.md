# HANDOFF — DASHBOARD_LIVE_GAME_MONITOR_001
## Live game-centered dashboard monitoring with clearer position/accounting truth

---

## STATUS: ACTIVE

This is a focused dashboard truth + monitoring usability fix.
Do not do a broad redesign.
Do not touch model logic.
Do not touch strategy.
Do not touch execution logic unless a tiny backend field addition is absolutely required.

---

## Pre-coding debug answers

### 1) What exact data is already available for live games?
Already available from `/api/games`:
- matchup
- score
- inning / inning half
- outs
- balls / strikes
- base occupancy
- game status
- hits / errors
- pitcher names when detail is available

### 2) What exact data is already available for open positions?
Already available from `/api/trades` and current frontend normalization:
- side
- entry price
- qty
- source
- TP / SL
- status
- confidence
- market slug

Already available via current matching enrichment:
- current price for the same market side when shadow rec matches slug
- matchup / team context
- live game context

Already available from `/api/state`:
- bankroll / net runtime state
- open positions summary

### 3) What tiny backend additions are needed?
A tiny backend addition is justified for accounting clarity:
- expose bankroll/accounting fields for:
  - capital committed in open trades
  - available cash
  - live position equity

This keeps accounting understandable without changing execution logic.

### 4) What should be the primary on-screen object?
**Hybrid live game + active position card**

If a live paper position exists for a game, that game/position card should be the primary monitoring object.

### 5) What should be pushed down into secondary space?
- trade log
- shadow diagnostics
- candidate/debug info

---

## Implementation direction

### Priority 1 — Position accounting / side truth
Make the card clearly show:
- exact bet side
- exact team/outcome being backed
- entry price for that side
- current price for that side
- live position value / equity in dollars
- unrealized PnL in dollars
- capital committed / size
- bankroll available cash vs capital in trades

### Priority 2 — Live game-centered monitoring
If a game has an active paper position, the card should emphasize:
- matchup
- score / inning / outs when available
- bet side
- entry
- current
- live equity
- unrealized PnL
- TP
- SL
- source

### Priority 3 — Information hierarchy
- live game + active position monitoring becomes primary
- trade log becomes secondary and scrollable
- diagnostics stay background only

### Priority 4 — Polymarket-like live feel without lying
Use existing polled data to make the monitoring view feel live-updating and market-aware, without inventing data.

---

## Acceptance criteria

1. user can instantly tell which games are live
2. user can instantly tell which live games have active positions
3. trade log no longer dominates the page
4. main monitoring view is game/position-centered
5. side/entry/current/PnL/value math is understandable
6. bankroll shows available cash vs tied-up capital more clearly
7. no truth regression
