# HANDOFF — DASH_012
## Fix game status chip — LIVE shown for unstarted games

---

## ✅ STATUS: ACTIVE — DASH_011 is APPROVED. You may proceed.

---

## Problem

Position cards show `i1 · LIVE` with a green dot for games in pre-game warmup. ESPN sends `inning=1` and `game_status="STATUS_IN_PROGRESS"` during warmup before first pitch. `gameStatusChip()` treats any truthy `inning` as LIVE.

**Do NOT touch**: `dashboard_server.py`, `launch_all.py`, `bot_core.py`, `core/`, `mlb_model/`

---

## Fix 1 — Update gameStatusChip() to use game_status field

**Location**: `dashboard.html` → `gameStatusChip()` function (lines ~666–670)

Find and replace the entire function:

```javascript
// BEFORE
function gameStatusChip(item) {
  if (item.resolved || item.status === 'closed') return 'FINAL';
  if (item.inning) return 'LIVE';
  return 'SCHEDULED';
}
```

```javascript
// AFTER
function gameStatusChip(item) {
  if (item.resolved || item.status === 'closed') return 'FINAL';
  const gs = (item.game_status || '').toUpperCase();
  if (gs.includes('FINAL') || gs.includes('POST')) return 'FINAL';
  if (gs.includes('PRE') || gs.includes('WARMUP') || gs.includes('SCHEDULED')) return 'SCHEDULED';
  if (gs.includes('PROGRESS') || gs.includes('LIVE')) return 'LIVE';
  if (item.inning && item.inning > 0) return 'LIVE';
  return 'SCHEDULED';
}
```

**Why**: Shadow recs carry a `game_status` field. Checking it first means warmup (`STATUS_PRE_GAME`) and scheduled games return `'SCHEDULED'` even if `inning=1`. Only games with `STATUS_IN_PROGRESS` or no `game_status` but a real inning return `'LIVE'`.

---

## Fix 2 — Only show live-dot and inning for live games

**Location**: `dashboard.html` → `buildUnifiedPositionCards()` → near line 684 (`inn` declaration) and line 721 (`gameCtxPill` build)

**Step A** — Find the `inn` declaration:
```javascript
const inn    = r.inning ? `i${r.inning}` : '';
```

**Step B** — Find the `gameCtxPill` build:
```javascript
const gameCtxPill = (game || inn) ? `<div class="game-ctx-pill"><span class="live-dot"></span>${game}${inn ? ' · ' + inn : ''} · ${gameStatusChip(r)}</div>` : '';
```

**Replace both** with:
```javascript
const statusChip = gameStatusChip(r);
const inn = (statusChip === 'LIVE' && r.inning) ? `i${r.inning}` : '';
const liveIndicator = statusChip === 'LIVE' ? '<span class="live-dot"></span>' : '';
```

And update the `gameCtxPill` line to:
```javascript
const gameCtxPill = game ? `<div class="game-ctx-pill">${liveIndicator}${game}${inn ? ' · ' + inn : ''} · ${statusChip}</div>` : '';
```

**Why**: The live-dot and inning number should only appear for genuinely live games. Scheduled/pre-game cards should show the matchup and `SCHEDULED` status only. The pill now shows even without an inning (previously `(game || inn)` could suppress the pill if both were empty — `game` is always set when slug parsing works so this is safe).

---

## Verification

Reload dashboard after saving:

1. **If LAD@WSN has not started**: card pill shows `LAD @ WSN · SCHEDULED` — no green dot, no inning number
2. **If LAD@WSN is live**: card pill shows `● LAD @ WSN · iN · LIVE` — green dot + inning
3. Check browser console — no JS errors
4. Open shadow feed or any in-game shadow card — verify LIVE status still works for genuinely live games

---

## Rollback

Revert `dashboard.html` only.
