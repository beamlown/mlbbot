# HANDOFF — DASH_007
## Simplify drawer — remove Markets and Signals tabs

---

## Context

The details drawer currently has 6 tabs: Trade Log, Shadow, Candidates, Markets, Signals, Manual. Markets and Signals are raw data dumps rarely useful in live operation and add tab clutter. This task removes them to leave 4 essential tabs.

DASH_002, DASH_003, DASH_004 are all complete — `dashboard.html` is now unlocked for this task.

---

## File to change

`sports_bot_v2/dashboard.html` — ONLY this file.

---

## Changes

### 1. Remove tab buttons

**Find in the tab-nav div (around where it now lives in the cmdbar/drawer area):**
```html
<button class="tab-btn" onclick="switchTab('markets',this)">Markets</button>
<button class="tab-btn" onclick="switchTab('signals',this)">Signals</button>
```

Delete both lines.

---

### 2. Remove tab panels

**Find and delete:**
```html
<div id="tab-markets" class="tab-panel">
  <div id="markets-list"><div class="empty-state">loading…</div></div>
</div>
```

**Find and delete:**
```html
<div id="tab-signals" class="tab-panel">
  <div id="signals-list"><div class="empty-state">loading…</div></div>
</div>
```

---

### 3. Remove JS fetch calls and render functions for markets and signals

In the polling/refresh JS, find any calls to `/api/markets` and `/api/signals` and delete them. Find any corresponding render functions (e.g. `renderMarkets()`, `renderSignals()`) and delete them. Also delete any variables that stored this data (e.g. `latestMarkets`, `latestSignals`).

---

### 4. Verify remaining tabs

After deletion, confirm these 4 tab buttons and panels still exist and are functional:
- Trade Log (`tab-trades`)
- Shadow (`tab-shadow`)
- Candidates (`tab-candidates`)
- Manual (`tab-manual`)

---

## Verification

```
cd C:\Users\johnny\Desktop\sports_bot_v2
python dashboard_server.py
```

Open `http://localhost:5000`, open drawer (hamburger menu). Count tab buttons — must be exactly 4: Trade Log, Shadow, Candidates, Manual. Click each to confirm content loads without JS errors.

## Rollback

Revert `dashboard.html` only.
