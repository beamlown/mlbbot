# HANDOFF — DASH_011
## Remove resolved paper trades from Positions panel

---

## Problem

Closed/resolved paper trade cards still render inside the Positions panel alongside live open trades. They should be removed from this panel — they're already visible in the Trade Log drawer.

**Do NOT touch**: `dashboard_server.py`, `launch_all.py`, `bot_core.py`, `core/`, `mlb_model/`

---

## Fix 1 — Remove resolvedPaper from unified array

**Location**: `dashboard.html` → `renderUnifiedPositions()` → line ~803

Find:
```javascript
const unified = [...enriched, ...shadowOnly, ...resolvedPaper];
```

Change to:
```javascript
const unified = [...enriched, ...shadowOnly];
```

Since `resolvedPaper` is no longer used, you can also remove the code that builds it. Find and remove this entire block (lines ~787–801):
```javascript
const resolvedPaper = closedTrades.map(t => {
    const rec = shadowRecs.find(r => r.market_slug === t.market_slug);
    return {
      ...t,
      ...(rec || {}),
      market_slug: t.market_slug,
      side: t.side,
      entry_px: t.entry_px,
      pnl_usd: t.pnl_usd,
      status: 'closed',
      resolved: true,
      _type: 'paper',
      _source: t.source,
    };
});
```

And remove the `closedTrades` declaration on line ~765:
```javascript
const closedTrades = trades.filter(t => t.status === 'closed').slice(0, 6);
```

---

## Fix 2 — Update empty state message

**Location**: `dashboard.html` → `renderUnifiedPositions()` → the empty state block just after `if (!unified.length)`

Find:
```javascript
$('positions-list').innerHTML = '<div class="empty-state">No active or recent positions</div>';
```

Change to:
```javascript
$('positions-list').innerHTML = '<div class="empty-state">No open positions</div>';
```

---

## Verification

Reload dashboard. With current state (1 open LAD@WSN trade, 2 closed SEA@LAA trades):

1. Positions panel shows **1 card** — the open LAD trade only
2. The 2 SEA@LAA RESOLVED cards are **gone** from the panel
3. Badge shows **1**
4. Open Trade Log drawer — closed SEA@LAA trades still appear there (unaffected)
5. No JS console errors

---

## Rollback

Revert `dashboard.html` only.
