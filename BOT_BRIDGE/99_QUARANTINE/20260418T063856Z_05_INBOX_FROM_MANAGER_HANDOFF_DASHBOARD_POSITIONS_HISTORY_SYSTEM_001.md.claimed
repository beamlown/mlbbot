# HANDOFF_DASHBOARD_POSITIONS_HISTORY_SYSTEM_001

## Status: HOLD_PENDING_EXECUTION_TRUTH

**Do not begin until:** `DASHBOARD_LIVE_COMMAND_CENTER_001` APPROVED.

---

## What this task is

Phase 3 of the redesign. **Populate the four secondary tabs.**

---

## Tab-by-tab rules

### POSITIONS tab
- Open positions: same current_held_price as LIVE tab (same SSE source — do NOT add a second price fetch)
- Closed positions: last 10, with team names, side direction, entry/exit, PnL, close reason
- No shadow data

### GAMES tab
- All games today: LIVE, SCHEDULED, FINAL
- Shadow advisory **IS** allowed here — but must be:
  - Labeled: `Advisory (not a position)`
  - Styled: muted/secondary CSS class (e.g. `.advisory`)
  - Visually distinct from position summaries
- If a position exists on a game, show it as a linked reference

### HISTORY tab
- Full trade log — NOT on main page (already demoted in shell phase)
- Team names, not raw slugs
- Side direction: "WIN" / "LOSE" backed_team label
- Entry, exit, PnL, size_usd, close reason, confidence
- Summary header: total trades, win rate, total PnL, avg PnL
- No shadow data

### SYSTEM tab
- Stream health: connection status, mark_count_received, last_hub_update age
- Fallback status: any position currently using stale marks?
- Process topology: bridge_enabled, ALLOW_LOCAL_MLB_ORIGINATION, loop stats
- Budget: odds_api call count
- Shadow engine stats: labeled "Shadow Engine (Advisory Only)"

---

## Key rules

- POSITIONS tab must use the same SSE price path as LIVE tab (not a second `/api/stream/state` connection)
- Advisory in GAMES tab must use CSS class `.advisory` with muted styling
- HISTORY must show team names — use the existing `slugToGameParts()` helper if it exists
- SYSTEM tab stream fields must come from `/api/state` — do not add a new diagnostics endpoint unless it already exists

---

## Deliverable check

- [ ] All 4 secondary tabs render without JS errors
- [ ] POSITIONS tab uses same SSE price source as LIVE tab
- [ ] GAMES tab advisory section has `.advisory` class and muted styling
- [ ] HISTORY shows team names, not slugs
- [ ] SYSTEM shows stream last-update age
- [ ] No shadow in POSITIONS or HISTORY tabs
- [ ] Mobile: all tabs usable at 390px
