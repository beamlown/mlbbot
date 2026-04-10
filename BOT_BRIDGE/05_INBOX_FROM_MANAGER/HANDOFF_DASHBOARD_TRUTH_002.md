# HANDOFF — DASHBOARD_TRUTH_002
## Unify dashboard around paper-execution truth with shadow demoted to diagnostics

---

## STATUS: PROVISIONAL_ACTIVE_PENDING_CLAUDE

This is the right next task after incident containment.
No implementation is being done in this step — this file is the provisional work order only.

---

## Debug conclusions

### 1) Main active positions panel source of truth
The **main Positions panel should be defined by real paper execution truth only**:
- source: `sports_bot_v2` trade DB / open paper trades
- practical feed path today:
  - `dashboard_server.py` → `_fetch_trades()`
  - frontend uses `latestTrades.filter(t => t.status === 'open')`

This is the only valid user-facing source for active positions.

### 2) Top-level counts / KPIs source of truth
Top-level user-facing counts should also come from paper execution truth only:
- open positions count → DB open paper trades
- realized/net bankroll → bot/runtime state / DB-backed realized truth
- live position count displays (`pos-count`, `cmd-open`, `kpi-open`) should all be anchored to the same DB-open-trades count

### 3) What shadow/advisory should remain visible as diagnostics only
Shadow should remain visible, but only in background/secondary diagnostics:
- shadow recommendation feed
- advisory history
- candidate/signal/debug context
- fair value / edge overlays that enrich real executed paper positions
- gate rejects / upstream reasoning

Shadow must not act like an alternate position universe.

### 4) Where key fields currently come from
#### Actual positions panel
- row existence: `dashboard.html` → `renderUnifiedPositions()` from `latestTrades` open trades
- entry price: DB trade row (`entry_px`)
- source: DB trade row (`source`)
- lifecycle state: DB trade `status`, plus status shaping in frontend
- current price: often from merged matching shadow rec (`current_price` via `...(rec || {})`)
- live PnL: recomputed in frontend for paper trades using DB qty + entry + current shadow-derived price
- TP / SL: from backend `_fetch_trades()` in `dashboard_server.py`
- matchup/team display: DB slug + optional shadow/home/away enrichment

#### KPIs / command bar
- mixed today between:
  - `/api/state` / runtime state (`renderState`)
  - DB/open-trade-derived values (`renderUnifiedPositions` overrides open counts)
  - shadow stats in shadow tab

### 5) What is still missing / stale / scattered / misleading
1. **Current price for live paper positions still depends on shadow rec merge**
   - if shadow match is absent/stale, card falls back poorly or shows less useful current-state info
2. **Top-level truth is still split across state vs DB timing**
   - counts can briefly lag when `/api/state` and DB refresh on different cycles
3. **Trade log / positions / state use overlapping but not fully unified field semantics**
   - source/status/open-count truths come from multiple layers with different refresh timing
4. **Shadow diagnostics are visually still close to core execution truth**
   - the UI is much better than before, but still feels like enriched subsystems stitched together rather than one clean assembly line
5. **Lifecycle clarity is incomplete**
   - user-facing panel should clearly read as execution lifecycle truth: open / resolved / final, with upstream diagnostics clearly separate

### 6) Exact files involved
#### Frontend
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html`

#### Backend truth adapter
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`

#### Runtime truth reference
- `C:\Users\johnny\Desktop\sports_bot_v2\runtime\state.json`

### 7) Minimal fix direction
The minimal next fix is **not** a redesign. It is a small truth-layer cleanup:

1. Keep **paper trades / DB-backed execution state** as the only source of user-facing active positions and counts
2. Move any remaining shadow-only semantics further into explicit diagnostics sections
3. Tighten backend/frontend field ownership so one layer defines:
   - row existence
   - counts
   - lifecycle state
   - TP/SL
   - source labels
4. Use shadow only for optional enrichment of executed positions:
   - matchup/game context
   - fair value / edge / current market context
5. Reduce timing drift between `/api/state` and DB-facing panels where possible, ideally by treating DB/open trades as the visual truth for positions while state remains operational telemetry

---

## Proposed implementation scope
Likely allowed files:
- `dashboard.html`
- `dashboard_server.py`

No bot logic redesign needed.
No execution logic redesign needed.
No model redesign needed.

---

## Why this is the right next task now
The incident work restored execution integrity and topology stability enough to move back up the stack.
Now the bottleneck is user-facing coherence:
- the backend can again be trusted as execution truth
- the dashboard still presents truth through a partially mixed state/shadow/DB lens
- the next highest-value task is making the dashboard present a single-system mental model instead of patched-together subsystems
