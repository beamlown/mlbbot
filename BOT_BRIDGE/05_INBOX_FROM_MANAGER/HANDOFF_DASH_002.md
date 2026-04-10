# HANDOFF — DASH_002
## Compact position cards — remove visual bloat

---

## Context

Position cards are currently enormous. Each card shows: a game context pill, team name, source badge, status badge, action pill, PnL (large), a probability track bar, 6 stat boxes (Entry / Current / Live PnL / TP / SL / Confidence), a confidence fill bar, a sparkline chart, and a reasons tag row.

The PnL is shown twice (pos-badge-col + stat box). The sparkline, prob track, and reasons row fill half the card with info that isn't needed at a glance.

This task removes the redundant and low-value elements so cards are roughly half their current height.

---

## File to change

`sports_bot_v2/dashboard.html` — ONLY this file.

Find function `buildUnifiedPositionCards()` around line 754.

---

## Changes

### 1. Remove probTrack

**Find (around line 803):**
```javascript
    const probTrack = buildProbTrack(r);
```

**And its use in the template (around line 820):**
```javascript
      ${probTrack}
```

Delete both lines entirely.

---

### 2. Remove sparkline

**Find (around line 804):**
```javascript
    const sparkline = buildSparkline(r.market_slug);
```

**And its use in the template (around line 854):**
```javascript
      ${sparkline}
```

Delete both lines entirely.

---

### 3. Remove reasons row

**Find (around line 856):**
```javascript
      ${reasons.length ? `<div class="reasons-row">${reasons.map(t=>`<span class="reason-tag">${t}</span>`).join('')}</div>` : ''}
```

**And the variable that feeds it (around line 802):**
```javascript
    const reasons = (r.reasons || []).slice(0, 3);
```

Delete both lines entirely.

---

### 4. Reduce pos-stats to 3 boxes: Entry, Current, Confidence

**Find the entire pos-stats div (around line 823–848):**
```html
      <div class="pos-stats">
        <div class="stat-box">
          <div class="stat-label">Entry</div>
          <div class="stat-val blue">${fmtPx(entry)}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">Current</div>
          <div class="stat-val gold">${fmtPx(r.current_price)}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">Live PnL</div>
          <div class="stat-val ${pnlSizeCls}">${pnlDisplay}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">TP</div>
          <div class="stat-val green">${fmtPx(r.tp_price)}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">SL</div>
          <div class="stat-val red">${fmtPx(r.sl_price)}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">Confidence</div>
          <div class="stat-val blue">${confPct}%</div>
        </div>
      </div>
```

**Replace with (3 boxes only — remove Live PnL, TP, SL):**
```html
      <div class="pos-stats">
        <div class="stat-box">
          <div class="stat-label">Entry</div>
          <div class="stat-val blue">${fmtPx(entry)}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">Current</div>
          <div class="stat-val gold">${fmtPx(r.current_price)}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">Confidence</div>
          <div class="stat-val blue">${confPct}%</div>
        </div>
      </div>
```

---

## What to keep

- Game context pill (`gameCtxPill`) — keep as-is
- `pos-top` row with team name, source badge, status/action/pnl badges — keep as-is
- `conf-wrap` confidence fill bar — keep as-is

---

## Verification

```
cd C:\Users\johnny\Desktop\sports_bot_v2
python dashboard_server.py
```

Open `http://localhost:5000`. Position cards should be noticeably shorter — no sparkline charts, no probability bars, no reason tags, and PnL appears once per card only.

## Rollback

Revert `dashboard.html` only.
