# HANDOFF — SYSTEM_UNIFY_001
## Unify dashboard truth — execution positions only, shadow demoted to diagnostics

---

## ✅ STATUS: ACTIVE — proceed immediately.

---

## The Problem

The dashboard is lying to the user.

`renderUnifiedPositions()` in `dashboard.html` builds the Positions panel from TWO sources:

1. **`enriched`** — real paper trades from DB (status='open'), optionally merged with matching shadow rec for live context
2. **`shadowOnly`** — shadow recommendations that have NO matching paper trade

Both get rendered as full position cards with WIN/LOSE pills, PnL numbers, TP/SL boxes, and OPEN status badges. The pos-count badge counts both. The user sees "4 open positions" when the DB has 1 real trade. The system looks like two competing tracking systems, not one assembly line.

The shadow log is an advisory/diagnostic feed. A model recommendation is not a position. Only executed trades are positions.

**Do NOT touch**: `dashboard_server.py`, `launch_all.py`, `bot_core.py`, `core/`, `mlb_model/`, `.env`

---

## Fix 1 — Remove shadowOnly from the Positions panel

Find `renderUnifiedPositions()` (~line 784). The current code looks like:

```javascript
const shadowOnly = shadowRecs
  .filter(r => r.action !== 'NO_TRADE' && !r.resolved)
  .filter(r => !openTrades.some(t => t.market_slug === r.market_slug))
  .map(r => ({ ...r, _type: 'shadow', _source: 'shadow' }));

const unified = [...enriched, ...shadowOnly];
$('pos-count').textContent = enriched.length + shadowOnly.length;
```

Replace with:

```javascript
const unified = enriched;
$('pos-count').textContent = enriched.length;
```

**Delete the entire `shadowOnly` const block** — it is no longer used.

**Do NOT touch** `renderShadow()`, `renderShadowFeed()`, `fetchShadow()`, or the Shadow drawer tab. Shadow data is still fetched every poll cycle and still renders in the Shadow tab. `shadowRecs` is still used above in the `enriched.map()` call for enrichment — keep that. Only the `shadowOnly` injection into `unified` is removed.

---

## Fix 2 — Live PnL uses actual paper qty, not shadow estimate

In `buildUnifiedPositionCards()`, find the line that sets `unrlzdUsd` (~line 719):

```javascript
const unrlzdUsd = r.unrealized_pnl_dollars ?? r.pnl_usd ?? null;
```

`r.unrealized_pnl_dollars` came from the shadow log's PnL computation, which always used `$50` as the position size. But after RISK_001, actual paper trades can be `$62.50` or `$75`. The computation is wrong.

Replace with:

```javascript
let unrlzdUsd;
if (r._type === 'paper' && r.qty != null && r.entry_px != null && r.current_price != null) {
  const isBuyYes = (r.side || r.action) === 'BUY_YES';
  unrlzdUsd = isBuyYes
    ? (r.current_price - r.entry_px) * r.qty
    : (r.entry_px - r.current_price) * r.qty;
  unrlzdUsd = Math.round(unrlzdUsd * 100) / 100;
} else {
  unrlzdUsd = r.unrealized_pnl_dollars ?? r.pnl_usd ?? null;
}
```

**How this works**:
- `r.qty` = actual contracts bought (from DB, via `_fetch_trades()`)
- `r.current_price` = shadow rec's current market price (merged in via `...(rec || {})` in `enriched`)
- If no shadow rec matched (current_price is null), falls through to `r.pnl_usd` (null for open trades → shows '—'), which is correct
- `r.entry_px` = actual paper fill price from DB

**Example**: trade opened at entry_px=0.41, current_price=0.53, qty=152.44 contracts (=$62.50/$0.41), BUY_YES:
- Old: `(0.53 - 0.41) * 50 = +$6.00` (shadow estimate)
- New: `(0.53 - 0.41) * 152.44 = +$18.29` (correct paper PnL)

---

## Fix 3 — Unify open count across all three display elements

After computing `enriched` in `renderUnifiedPositions()`, add bindings so pos-count, kpi-open, and cmd-open all show the same number:

```javascript
const unified = enriched;
$('pos-count').textContent = enriched.length;
$('kpi-open').textContent = enriched.length;    // ADD THIS
$('cmd-open').textContent = enriched.length;    // ADD THIS
```

`renderState()` sets `kpi-open` and `cmd-open` from `state.open_positions` (state.json written by bot_core). That file can lag by one loop cycle. `renderUnifiedPositions()` runs after every `fetchShadow()` and `fetchTrades()` call, so these bindings here will always reflect DB truth and will dominate.

---

## What NOT to change

- `fetchShadow()` — still called every poll
- `latestShadowData` — still populated
- The `enriched.map()` block and the `const rec = shadowRecs.find(...)` lookup — shadow enrichment stays
- `renderShadow()` and `renderShadowFeed()` — Shadow tab still works
- The `sourceBadge()` function — still used on `_type: 'paper'` enriched cards
- Any server-side files

---

## What the system looks like after this fix

```
POSITIONS PANEL (left column):
  ← only paper trades (DB status='open'), enriched with game context from shadow log
  ← pos-count = kpi-open = cmd-open = len(DB open trades)
  ← if 0 open trades: "No open positions"

SHADOW TAB (drawer, right column):
  ← all model recommendations for today's games
  ← ticker rows with edge%, team, action label, status
  ← stats: signals count, no-trade count, shadow win rate, shadow P&L
  ← this is diagnostic/advisory — NOT shown as positions

FLOW:
  model rec → [bridge gate] → paper_exec → DB open trade → position card
                          ↘ rejected/unexecuted → shadow tab only
```

---

## Verification

1. Open dashboard. Count position cards in the main panel.
2. Compare to `curl http://localhost:8900/api/trades | python -m json.tool` — count `"status": "open"` entries. Numbers must match.
3. pos-count badge = kpi-open KPI = cmd-open in command bar. All three identical.
4. Open Shadow tab in drawer — shadow ticker rows still appear there.
5. Browser console: no JS errors.
6. If you have 1 real open trade and shadow log has 4 recs — Positions panel shows **1 card**, not 5.

---

## Rollback

Revert `dashboard.html` only.
