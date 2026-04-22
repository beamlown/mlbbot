# HANDOFF_DASHBOARD_LIVE_COMMAND_CENTER_001

## Status: HOLD_PENDING_EXECUTION_TRUTH

**Do not begin until:** `DASHBOARD_REDESIGN_SHELL_001` APPROVED.

---

## What this task is

Phase 2 of the redesign. **Populate the LIVE tab with real data.**

Three sections, top to bottom:
1. **Live game monitor** — game cards sorted by position presence, then live, then scheduled
2. **Active position cards** — held-contract truth, backed_team semantics
3. **Account strip** — bankroll, committed, win rate, expectancy

**Primary allowed file: `dashboard.html`**
`dashboard_server.py` only if a field is provably absent from existing API responses.

---

## CRITICAL: Pricing truth rules — BACKEND OWNS HELD-SIDE NORMALIZATION

The SSE `positions_mark` event already delivers `current_price` — a normalized field that the backend has already set to `bid_yes` (BUY_YES) or `bid_no` (BUY_NO). **The frontend must not redo this work.**

### The only correct frontend pattern:
```javascript
// CORRECT — use what the backend already normalized
const currentPrice = position.current_price;
const unrealizedPct = (currentPrice - position.entry_px) / position.entry_px;
```

### Hard reject — do not write this:
```javascript
// REJECTED — frontend must not branch on side to pick bid_yes/bid_no
const currentPrice = trade.side === 'BUY_YES' ? mark.bid_yes : mark.bid_no;
```

**Why:** The backend (`core/risk.py`, `core/paper_exec.py` — normalized in EXECUTION_HELD_SIDE_SEMANTICS_001) and the SSE server already apply held-side normalization. A second frontend derivation is a competing price writer and re-opens the risk of the SEA/TEX incident at the display layer.

**Exception:** If `positions_mark.current_price` is genuinely absent from the SSE payload (verify by inspecting the actual event), document that absence explicitly in the result. Do not assume it is absent — check first.

---

## Position card required fields

```
[LAD WIN]  Backing LAD  Fading SD
Entry:  0.41    Current: 0.62 ▲    Unr: +51.2%
TP: 0.76    SL: 0.33    Size: $50.00    Conf: 72%
Live equity: $31.00
```

- `backed_team` large and prominent
- `current_held_price` shows `bid_no` for BUY_NO, `bid_yes` for BUY_YES
- STALE badge if SSE last update > 30s
- No raw market slug visible
- No shadow/advisory data

---

## SSE update path

Position cards must update current price **in-place** on each SSE `positions_mark` event:
- Do NOT re-render the full card list on each tick
- Find the DOM element by trade ID and update only the price and unrealized fields

---

## Preflight: inspect the SSE payload first

Before writing any pricing JS, read the actual SSE `positions_mark` event and list every field it contains. If `current_price` is present, use it and stop. If it is absent, document this explicitly in your result — then and only then may you derive from `bid_yes`/`bid_no`.

## Deliverable check

- [ ] LIVE tab renders with all 3 sections
- [ ] Current price is read from `positions_mark.current_price` — no `bid_yes`/`bid_no` branch in frontend
- [ ] grep for `bid_yes` and `bid_no` in new LIVE tab JS: both absent from price logic
- [ ] unrealized_pct derived from `current_price` (not from `bid_yes`/`bid_no`)
- [ ] unrealized sign correct (positive when position is profitable)
- [ ] backed_team shown, no raw slug
- [ ] STALE badge logic present
- [ ] SSE updates in-place (no full card list re-render)
- [ ] Account strip shows r25.win_rate
- [ ] No shadow data in LIVE tab
- [ ] Zero JS errors
