# Skill: State Consistency Debugger

Rules for keeping dashboard state consistent across renders.

## The normalization pattern (mandatory)
Always normalize `open_positions` once in `renderState`, then pass the normalized array everywhere:

```js
const positions = Array.isArray(s.open_positions)
  ? s.open_positions.filter(p => p && typeof p === 'object')
  : [];
$('kpi-open').textContent = positions.length;
renderBotPositions(positions);
```

Never call `(s.open_positions || []).length` in one place and `s.open_positions || []` in another — they can diverge if the state object is mutated or partially populated.

## Known mismatch root causes
1. **Race condition**: `fetchState()` and `fetchShadow()` resolve at different times; KPI renders from one response while panel renders from another.
2. **Null entries in array**: `state.open_positions` sometimes contains null/undefined entries when the bot is starting up. The filter `p => p && typeof p === 'object'` removes these.
3. **Stale cached state**: Old tab still open with old JS → hard refresh fixes.
4. **Multiple poll loops**: Only one `setInterval(poll, 10000)` should exist. Search for duplicate `setInterval` calls.

## Diagnostic checklist
- [ ] Open browser DevTools → Network tab → watch `/api/state` responses
- [ ] Confirm `open_positions` field shape in raw JSON (is it array? are there nulls?)
- [ ] Search for `kpi-open` in JS — should only be set in one place (inside `renderState`)
- [ ] Search for `renderBotPositions` — should only be called from `renderState`
- [ ] Confirm no duplicate `setInterval` or `fetchState` calls

## Shadow positions vs bot positions
These are DIFFERENT concepts:
- **Bot positions** = `state.open_positions` from `/api/state` — actual paper trades
- **Shadow positions** = unresolved recs from `/api/mlb-shadow` — model signals, no real money
Keep them in separate UI sections with clear labels.
