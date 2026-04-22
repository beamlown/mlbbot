# HANDOFF — DASH_016
## Trade log: team name display, USD size, command bar win rate binding

---

## ✅ STATUS: ACTIVE — DASH_015 APPROVED. Proceed immediately.

---

## Context

After DASH_015 is approved, this task finishes the trade log polish:

1. Trade log shows raw market slugs (`mlb-sea-laa-2026-04-05`) truncated to 30 chars — should show `SEA @ LAA`
2. Trade log shows no position size in USD — `qty * entry_px` is available
3. Command bar win rate binding — verify it's wired (DASH_015 may have already done this)

`slugToGameParts()` was added in DASH_009 and is available globally in the file.

**Do NOT touch**: `dashboard_server.py`, `launch_all.py`, `bot_core.py`, `core/`, `mlb_model/`, `.env`

---

## Fix 1 — Trade log team names

In `renderTrades()`, find where the market slug is displayed. It probably looks like:

```javascript
const ss = slug.length > 30 ? slug.slice(0, 30) + '…' : slug;
// or similar truncation
```

Replace slug display with:

```javascript
const _sp = slugToGameParts(slug);
const teamDisplay = _sp ? `${_sp.away} @ ${_sp.home}` : (slug ? slug.slice(0, 22) + '…' : '?');
```

Use `teamDisplay` in the card template wherever the slug was shown.

---

## Fix 2 — Trade log USD size

In `renderTrades()`, before the card template string, compute:

```javascript
const sizeUsd = (t.qty && t.entry_px) ? fmtUsd(t.qty * t.entry_px) : '—';
```

Add to the trade card template (next to or below the side pill):

```html
<span class="trade-size">${sizeUsd}</span>
```

---

## Fix 3 — Command bar win rate binding (conditional)

Check if DASH_015 already added the `cmd-winrate` binding in `updateState(s)`.

- If the binding is already there: **skip this fix entirely.**
- If the binding is missing (the `<b id="cmd-winrate">` element exists but nothing updates it), add to `updateState(s)` alongside the `cmd-open`/`cmd-pnl` bindings:

```javascript
const wr = s?.r25?.win_rate;
$('cmd-winrate').textContent = wr != null ? (wr * 100).toFixed(0) + '%' : '—';
```

---

## Verification

1. Open dashboard → Trades log/tab
2. Every trade card shows **SEA @ LAA** style (not raw slug)
3. Every trade card shows a **dollar amount** (e.g. $50.00)
4. Command bar **W%:** updates on page refresh
5. Browser console: no JS errors

---

## Rollback

Revert `dashboard.html` only.
