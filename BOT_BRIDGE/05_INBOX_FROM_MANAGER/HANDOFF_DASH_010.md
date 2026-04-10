# HANDOFF — DASH_010
## Fix section title and badge count — "Active Positions" confusion

---

## ✅ STATUS: ACTIVE — DASH_009 is APPROVED. You may proceed.

---

## Problem summary

The section header says "Active Positions" with a badge showing `2`, while the command bar simultaneously shows `Open: 0`. Both are technically correct but count different things, making the UI contradictory at a glance.

- `pos-count` badge = `unified.length` = open + shadow + **resolved** = 2
- `cmd-open` = `state.json open_positions.length` = truly open bot positions = 0

**Do NOT touch**: `dashboard_server.py`, `launch_all.py`, `bot_core.py`, `core/`, `mlb_model/`

---

## Fix A — Rename section title

**Location**: `dashboard.html` line 351

Find:
```html
<span class="section-title">Active Positions</span>
```

Change to:
```html
<span class="section-title">Positions</span>
```

---

## Fix B — Badge counts only live positions

**Location**: `dashboard.html` → `renderUnifiedPositions()` → line ~796

Find:
```javascript
$('pos-count').textContent = unified.length;
```

Change to:
```javascript
$('pos-count').textContent = enriched.length + shadowOnly.length;
```

`enriched` = open paper trades, `shadowOnly` = shadow-only advisory positions. Both variables are already defined earlier in `renderUnifiedPositions()` before this line. Resolved paper cards (`resolvedPaper`) are still rendered in the list — they just don't inflate the badge.

---

## Verification

After save, reload the dashboard:

1. Section header reads **"Positions"** — not "Active Positions"
2. With current state (0 open, 0 shadow, 2 resolved): badge shows **0** — not 2
3. The 2 resolved paper cards are still visible in the list (not hidden)
4. No JS console errors

---

## Rollback

Revert `dashboard.html` only. No server files touched.
