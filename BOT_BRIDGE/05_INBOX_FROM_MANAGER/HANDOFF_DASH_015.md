# HANDOFF — DASH_015
## Position card: WIN/LOSE direction, TP/SL/Size boxes, command bar win rate

---

## ✅ STATUS: ACTIVE — proceed immediately.

---

## Context

Three UI improvements to `dashboard.html`. The server already returns the needed data (`tp_price`, `sl_price`, `qty`, `entry_px`, `r25.win_rate`) — this is purely a display task.

**Do NOT touch**: `dashboard_server.py`, `launch_all.py`, `bot_core.py`, `core/`, `mlb_model/`, `.env`

---

## Fix 1 — YES/NO pill → WIN/LOSE

In `buildUnifiedPositionCards()`, find the line that sets `aLabel`. Currently it's something like:

```javascript
const aLabel = isYes ? 'YES' : 'NO';
```

Replace with:

```javascript
const aLabel = isYes ? 'WIN' : 'LOSE';
```

**Why**: `isYes` means we hold a YES contract on this market. YES wins when the tracked team wins. So `isYes → 'WIN'` means "we're backing this team to win." `!isYes → 'LOSE'` means "we're betting against this team." This is immediately readable on mobile without knowing contract semantics.

---

## Fix 2 — Add TP, SL, Size stat boxes

The position cards currently show 3 stat boxes: Entry, Current, Confidence. We need 3 more: TP, SL, Size.

In `buildUnifiedPositionCards()`, **before** the stat boxes template string, compute size:

```javascript
const sizeUsd = (r.qty != null && r.entry_px != null)
    ? fmtUsd(r.qty * r.entry_px)
    : (r.shadow_position_size_usd ? fmtUsd(r.shadow_position_size_usd) : '—');
```

Then in the `.pos-stats` template block, after the existing 3 boxes, append:

```html
<div class="stat-box"><div class="stat-label">TP</div><div class="stat-val green">${fmtPx(r.tp_price)}</div></div>
<div class="stat-box"><div class="stat-label">SL</div><div class="stat-val red">${fmtPx(r.sl_price)}</div></div>
<div class="stat-box"><div class="stat-label">Size</div><div class="stat-val">${sizeUsd}</div></div>
```

The `.pos-stats` CSS already uses `grid-template-columns: repeat(3, 1fr)`. Adding 3 more boxes will auto-wrap to a second row — no CSS change needed.

**Helper note**: `fmtPx` formats a decimal price (should already exist in dashboard.html). If it doesn't exist, use: `const fmtPx = v => v != null ? v.toFixed(2) : '—';`

**Shadow positions**: Shadow positions may not have `qty`/`entry_px` — they use `shadow_position_size_usd` instead. The fallback handles this. Shadow positions also won't have `tp_price`/`sl_price` from the server — `fmtPx(null)` will show '—' which is fine.

---

## Fix 3 — Command bar win rate

**Step A** — Find the command bar HTML. It has `cmdbar-stat` spans for Open count and P&L. Add after them:

```html
<span class="cmdbar-stat">W%: <b id="cmd-winrate">—</b></span>
```

**Step B** — In `updateState(s)` (the function that runs on each `/api/state` poll), find where `cmd-open` and `cmd-pnl` are bound, and add:

```javascript
const wr = s?.r25?.win_rate;
$('cmd-winrate').textContent = wr != null ? (wr * 100).toFixed(0) + '%' : '—';
```

This feeds from DASH_014's `r25.win_rate`. If DASH_014 isn't running yet, `s?.r25` will be undefined and '—' shows — safe fallback.

---

## Verification

1. Open dashboard (any browser, preferably narrow/mobile view)
2. Any open position card: pill shows **WIN** or **LOSE** (not YES/NO)
3. Any open position card: 6 stat boxes visible — bottom row shows TP (green), SL (red), Size ($)
4. Top command bar: **W%: —** or **W%: 62%** etc. is visible
5. Browser console: no JS errors

---

## Rollback

Revert `dashboard.html` only.
