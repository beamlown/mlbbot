# HANDOFF — DASHBOARD_RESTORE_BASEBALL_MONITOR_001
## Restore baseball-monitor-first active cards while preserving truth/accounting fixes

---

## STATUS: ACTIVE

This is a controlled restore-and-wire task.
It is not a broad redesign.
It must restore the richer baseball-monitor feel without losing the newer truth/accounting fixes.

---

## Hard requirements

### Baseball monitor detail must be visible on the main active card when available
- score
- inning
- inning half
- outs
- balls / strikes if available
- base occupancy / runners on base
- pitcher name(s) if available
- live game status

### Main active object must feel like
- a live baseball game card first
- a trade/position card second
- not a trade card with tiny game metadata

### Trade log must remain secondary
- lower on the page
- visually quieter
- not the thing the eye lands on first

### Position semantics must stay correct
- exact held side / outcome
- entry price for held side
- current price for held side
- live equity
- unrealized PnL
- committed capital
- TP / SL
- source

### Bankroll/accounting must stay truthful
- available cash reflects open committed capital
- capital in trades does not drop to zero when a trade is open
- live equity and unrealized remain internally consistent

---

## Pre-coding decisions

1. Base occupancy will be rendered directly on the main active card using the existing baseball diamond/base-state visual driven by on_first/on_second/on_third.
2. Pitcher info will appear in the main game-state detail block of the active card, not in diagnostics.
3. The primary focal area is the active live baseball monitor card section above the fold.
4. Trade log remains secondary in the lower drawer/tab area and must not retake default emotional ownership.
5. Current accounting fields are expected to be sufficient; prefer dashboard.html-only unless a tiny support field proves necessary.

---

## Acceptance criteria

1. main active card visibly shows baseball-state detail when available
2. user can tell what is happening in the game right now
3. user can tell exactly what the bot is holding
4. trade log is no longer the emotional center of the page
5. accounting numbers make sense together
6. no truth regression
