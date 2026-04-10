# HANDOFF — DASH_013
## Fix shadow feed ticker — inning shown for pre-game recs

---

## ✅ STATUS: ACTIVE — proceed immediately.

---

## Problem

`renderShadowFeed()` in `dashboard.html` has the same pre-game inning bug that DASH_012 fixed on position cards. Line 898:

```javascript
const inn    = r.inning ? ` i${r.inning}` : '';
```

This appends inning text whenever `r.inning` is truthy — including warmup/pre-game recs where ESPN reports `inning=1` before first pitch. Shadow ticker rows show `SEA@LAA i1` for a game that hasn't started.

`gameStatusChip()` was already corrected in DASH_012 and is available globally. Reuse it.

**Do NOT touch**: `dashboard_server.py`, `launch_all.py`, `bot_core.py`, `core/`, `mlb_model/`

---

## Fix — renderShadowFeed() line ~898

Find:
```javascript
const inn    = r.inning ? ` i${r.inning}` : '';
```

Replace with:
```javascript
const statusChip = gameStatusChip(r);
const inn = (statusChip === 'LIVE' && r.inning) ? ` i${r.inning}` : '';
```

The `statusChip` variable is local to the `shown.map(r => { ... })` callback. No conflicts with other variables.

---

## Verification

Open dashboard → Shadow tab (drawer):

1. Rec for a pre-game/unstarted game: game column shows `AWAY@HOME` — no inning suffix
2. Rec for a live in-game game: game column shows `AWAY@HOME i3` (current inning)
3. No JS console errors

---

## Rollback

Revert `dashboard.html` only.
