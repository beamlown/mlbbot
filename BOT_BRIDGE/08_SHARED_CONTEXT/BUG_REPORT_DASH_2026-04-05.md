# Dashboard Bug Report — 2026-04-05
## Source: Screenshot analysis + full code read

---

## What the screenshot showed

- Command bar: `Open: 0  P&L: +$30.79  Loop: 8`
- **Active Positions** badge: `2`
- Both cards:
  - Badge: `PAPER-MODEL`
  - Action: `NO`
  - Status: `RESOLVED_WIN` / `RESOLVED_LOSS`
  - Team: `mlb-se` (mangled)
  - Entry: `48.2¢` / `62.3¢`
  - Current: `—`
  - Realized $: `—`

---

## Bug 1 — CRITICAL: Resolved paper trade cards show "—" for PnL and Current price

**File**: `dashboard.html`
**Functions**: `buildUnifiedPositionCards()` (line 668), `renderUnifiedPositions()` (line 753)

### Root cause

`buildUnifiedPositionCards()` uses two shadow-specific field names:
- `r.unrealized_pnl_dollars` → for the PnL display (line 710)
- `r.current_price` → for the Current stat box (line 738)

For resolved paper trades (`resolvedPaper` array), the object is built from the DB row spread (`...t`). The DB row has:
- `pnl_usd` — the actual realized P&L in dollars
- `exit_px` — the price at close

But neither `unrealized_pnl_dollars` nor `current_price` exists on DB rows. They are shadow rec fields only. Result: both show `"—"` for every closed paper trade.

### Fix

In `buildUnifiedPositionCards()`:
```javascript
// line 704 area — add fallback to pnl_usd
const unrlzdUsd = r.unrealized_pnl_dollars ?? r.pnl_usd ?? null;

// line 738 area — add fallback to exit_px for resolved positions
const currentPx = r.current_price ?? (r.resolved ? r.exit_px : null);
// then use currentPx instead of r.current_price in the stat box
```

---

## Bug 2 — CRITICAL: Team name shows "mlb-se" (mangled slug)

**File**: `dashboard.html`
**Line**: 720

### Root cause

For closed paper trades where no matching shadow rec is found (yesterday's games are now date-filtered), `r.tracked_team` and `r.home_team` are both null.

Line 720 falls back to:
```javascript
shortTeam(r.home_team || r.market_slug || '?')
// → shortTeam("mlb-sea-laa-2026-04-04")
// → "mlb-sea-laa-2026-04-04".split(' ').pop().slice(0,6)
// → "mlb-se"
```

`TEAM_ABBR` (line 459) maps full names like `"Seattle Mariners"` to `"SEA"` — slug abbreviations like `"sea"` are NOT in the map.

### Fix

Add a slug parser helper that extracts the away/home abbreviation pair from the `mlb-AWAY-HOME-YYYY-MM-DD` format:

```javascript
function slugToGameParts(slug) {
  const m = (slug||'').match(/^mlb-([a-z]+)-([a-z]+)-\d{4}-\d{2}-\d{2}$/);
  if (!m) return null;
  return { away: m[1].toUpperCase(), home: m[2].toUpperCase() };
}
```

Use it in `buildUnifiedPositionCards()` as a fallback when `r.away_team` / `r.home_team` are null:
```javascript
const slugParts = (!r.home_team && !r.away_team) ? slugToGameParts(r.market_slug) : null;
const homeTeam  = r.home_team || slugParts?.home || null;
const awayTeam  = r.away_team || slugParts?.away  || null;
const game      = awayTeam && homeTeam ? `${awayTeam} @ ${homeTeam}` : '';
const teamDisplay = r.tracked_team || game || shortTeam(r.market_slug || '?');
```

This also restores the `game` context variable for the `gameCtxPill`, which is currently blank for closed paper trades.

---

## Bug 3 — UX: "Active Positions: 2" contradicts "Open: 0" in command bar

**File**: `dashboard.html`
**Lines**: 351 (section title), 796 (`pos-count`)

### Root cause

Two different counters:
- `cmd-open` (command bar) = `state.json.open_positions.length` = **0** (truly open bot positions)
- `pos-count` (section badge) = `unified.length` = **2** (open + shadow + resolved combined)

These are shown side-by-side but count completely different things. A user reading the screen sees "Active Positions: 2" and "Open: 0" at the same time and has no way to reconcile them.

### Fix

Two changes:
1. Rename section title from `"Active Positions"` → `"Positions"` (line 351)
2. Change `$('pos-count').textContent` to only count open + shadow, not resolved:
```javascript
const openCount = enriched.length + shadowOnly.length;
$('pos-count').textContent = openCount;
// (still render all unified cards including resolvedPaper, but badge only counts live)
```

---

## Bug 4 — MINOR: "realized $" label but value shows "—"

**File**: `dashboard.html`
**Line**: 712, 727

### Root cause

`pnlEstLabel` correctly detects `r.resolved === true` and shows `"realized $"`. But `pnlDisplay` is `"—"` because of Bug 1. Once Bug 1 is fixed, this resolves automatically.

No separate fix needed — fixed by Bug 1 patch.

---

## Bug 5 — MINOR: Game context pill missing for closed paper trades

**File**: `dashboard.html`
**Line**: 714

### Root cause

`gameCtxPill` requires `r.away_team && r.home_team`. For closed paper trades without shadow enrichment, both are null → pill is blank. Fixing Bug 2 (slug parser) also restores the away/home fields for this pill.

No separate fix needed — fixed by Bug 2 patch.

---

## Known issues / deferred

| Issue | Location | Notes |
|-------|----------|-------|
| `tp_price = 0.85` hardcoded for BUY_NO (wrong side) | `dashboard_server.py:250` | Not currently displayed in UI — deferred |
| `current_price` always null for open paper trades with no shadow match | `dashboard.html` | Shadow enrichment covers most cases; low risk for now |

---

## Work order plan

| Order | task_id | Description | File | Status |
|-------|---------|-------------|------|--------|
| 1 | DASH_009 | Fix position card data: PnL, Current price, team name from slug | `dashboard.html` | → ACTIVE |
| 2 | DASH_010 | Fix section clarity: rename title, fix badge count | `dashboard.html` | → QUEUED (same file) |
