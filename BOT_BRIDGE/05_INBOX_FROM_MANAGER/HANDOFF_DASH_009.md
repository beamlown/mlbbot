# HANDOFF — DASH_009
## Fix resolved paper trade cards: PnL, Current price, team name

---

## Problem summary

Resolved paper trade cards show `—` for both PnL and Current price, and display `mlb-se` (mangled slug) instead of team names. Three code-level bugs, all in `dashboard.html`.

**Do NOT touch**: `dashboard_server.py`, `launch_all.py`, `bot_core.py`, `core/`, `mlb_model/`

---

## Fix 1 — PnL display: fallback to `pnl_usd`

**Location**: `dashboard.html` → `buildUnifiedPositionCards()` → near line 704

Find this line:
```javascript
const unrlzdUsd = r.unrealized_pnl_dollars;
```

Change to:
```javascript
const unrlzdUsd = r.unrealized_pnl_dollars ?? r.pnl_usd ?? null;
```

**Why**: `unrealized_pnl_dollars` is a shadow rec field. Paper trades from the DB carry `pnl_usd` (the realized dollar P&L). Adding `?? r.pnl_usd` means resolved paper trades show their actual P&L from the DB.

---

## Fix 2 — Current stat box: fallback to `exit_px`

**Location**: `dashboard.html` → `buildUnifiedPositionCards()` → near line 738

Find the `pos-stats` HTML block. Just before the `<div class="pos-stats">` line, add:
```javascript
const currentPx = r.current_price ?? (r.resolved ? r.exit_px : null);
```

Then change the Current stat box from:
```html
<div class="stat-val gold">${fmtPx(r.current_price)}</div>
```
To:
```html
<div class="stat-val gold">${fmtPx(currentPx)}</div>
```

**Why**: `current_price` is a shadow rec field (live market ask price). For resolved paper trades there is no live market. The DB stores the final trade price as `exit_px`. For non-resolved positions, we keep the existing behavior (`r.current_price`).

---

## Fix 3 — Team display: add slug parser

**Location A**: `dashboard.html` → near line 471 (right after `shortTeam` definition)

Add this new helper:
```javascript
const slugToGameParts = slug => {
  const m = (slug||'').match(/^mlb-([a-z]+)-([a-z]+)-\d{4}-\d{2}-\d{2}$/);
  return m ? { away: m[1].toUpperCase(), home: m[2].toUpperCase() } : null;
};
```

**Location B**: `dashboard.html` → `buildUnifiedPositionCards()` → near line 676–677

Find and replace the `game` declaration:
```javascript
const game   = r.away_team && r.home_team ? `${shortTeam(r.away_team)} @ ${shortTeam(r.home_team)}` : '';
```

Replace with:
```javascript
const _slugParts = (!r.home_team && !r.away_team) ? slugToGameParts(r.market_slug) : null;
const _homeTeam  = r.home_team || (_slugParts && _slugParts.home) || null;
const _awayTeam  = r.away_team || (_slugParts && _slugParts.away) || null;
const game = _awayTeam && _homeTeam ? `${_awayTeam} @ ${_homeTeam}` : '';
```

**Location C**: `dashboard.html` → `buildUnifiedPositionCards()` → near line 720

Find:
```javascript
<div class="pos-team">${r.tracked_team || shortTeam(r.home_team || r.market_slug || '?')}</div>
```

Replace with:
```javascript
<div class="pos-team">${r.tracked_team || game || shortTeam(r.market_slug || '?')}</div>
```

**Why**: When closed paper trades have no matching shadow rec (yesterday's games are date-filtered out), `r.home_team` and `r.away_team` are null. The slug `mlb-sea-laa-2026-04-04` encodes the teams as lowercase abbreviations. The new helper extracts them as uppercase: `{ away: 'SEA', home: 'LAA' }`. This also restores the `gameCtxPill` display which also reads from `game`.

---

## Verification

After save (dashboard auto-serves from the running process):

1. Reload the dashboard in browser.
2. The two resolved paper trade cards (`mlb-sea-laa-2026-04-04`) should now show:
   - **PnL**: a dollar amount (e.g. `+$53.00` or `-$22.21`) — **not** `—`
   - **Current**: a price in cents (the exit price, e.g. `100.0¢` for resolved YES) — **not** `—`
   - **Team**: `SEA @ LAA` — **not** `mlb-se`
3. Open browser console — no new JS errors.
4. If any live open positions exist, verify they still render correctly (no regression on shadow cards).

---

## Rollback

Revert `dashboard.html` only. The server (`dashboard_server.py`) is not touched by this task.
