# HANDOFF — DASHBOARD_REWORK_001
## Dashboard redesign: command-centric HUD, unified positions panel

---

## What you are doing

Rebuilding `sports_bot_v2/dashboard.html` (and minor `dashboard_server.py` if needed) so the dashboard leads with trade execution context, not shadow advisory framing.

**The current problem:** The left column gives "Shadow Advisory Feed" equal visual weight to "Active Positions." The HUD is labeled "Shadow P&L." The dashboard was built before paper execution existed. It needs to be reframed around what actually matters: are paper trades open, what are they doing, are they winning.

---

## Files you may touch

- `sports_bot_v2/dashboard.html` (primary — most of your work is here)
- `sports_bot_v2/dashboard_server.py` (only if a minor additive change is truly needed)

**Do NOT touch:** `core/`, `bot_core.py`, `launch_all.py`, `mlb_model/`

---

## What the APIs already give you (no new backend work expected)

| API | Key fields |
|-----|-----------|
| `/api/mlb-shadow?limit=30` | `recs[]`: market_slug, action, fair_win_prob, **entry_price**, **current_price**, **tp_price**, **sl_price**, **unrealized_pnl_dollars**, **status_label**, resolved, away_team, home_team, inning, tracked_team, confidence, edge_yes/no, ts |
| `/api/trades?limit=60` | `trades[]`: market_slug, side, entry_px, exit_px, pnl_usd, **status** (open/closed), **source** (bot/model_bridge/manual), confidence, ts_open |
| `/api/state` | open_positions[], bankroll, r25, mode, loop_count, stale |
| `/api/games` | ESPN scoreboard, live scores, inning, base runners |

---

## 4-change summary

### Change 1 — HUD strip relabeled
Current: `Shadow P&L | Win Rate | Active | Unrlzd P&L`
New: `SYSTEM (bot dot + loop) | MODE (badge) | POSITIONS (paper open count) | LIVE P&L (unrealized dollars)`

- `hud-pnl` label → "Live P&L"
- `hud-wr` → repurpose as Mode display OR keep win rate but label it "Win Rate" not "Shadow"
- `hud-active` → count from `open_positions.length` (paper), not shadow unresolved
- `hud-unrlzd` → keep, label "Live P&L $"
- Remove "Shadow Advisory" subtitle line below HUD

### Change 2 — Unified Positions panel (left column, single section)
Replace the two left-column sections (Active Positions + Shadow Advisory) with ONE section: **Active Positions**.

**Data fetch:** Call both `/api/mlb-shadow` and `/api/trades`. Build a merged array:

```
// Paper open trades (source=bot/model_bridge/manual)
openTrades = trades.filter(t => t.status === 'open')

// Enrich each paper trade with shadow rec data if slug matches
enriched = openTrades.map(t => {
  const rec = shadowRecs.find(r => r.market_slug === t.market_slug)
  return { ...t, ...rec, _type: 'paper', _source: t.source }
})

// Shadow-only recs (no matching open paper trade)
shadowOnly = shadowRecs
  .filter(r => r.action !== 'NO_TRADE' && !r.resolved)
  .filter(r => !openTrades.some(t => t.market_slug === r.market_slug))
  .map(r => ({ ...r, _type: 'shadow', _source: 'shadow' }))

unified = [...enriched, ...shadowOnly]
```

**Each card shows:**
- Matchup: `away_team @ home_team` (from rec) or slug short-form
- Side pill (YES/NO)
- **Source badge**: 
  - `PAPER-BOT` (source=bot) — green border
  - `PAPER-MODEL` (source=model_bridge) — blue border  
  - `MANUAL` (source=manual) — gold border
  - `SHADOW` (shadow-only) — dim border, italic
- Entry price, Current price, Live PnL ($), TP, SL, Confidence
- Game status chip: LIVE / FINAL / SCHEDULED (from inning field or games cross-reference)
- Status badge: OPEN / RESOLVED_WIN / RESOLVED_LOSS / SL_ZONE

Keep the existing `prob-track-v2` component — it already renders correctly given entry/current/tp/sl values. Pass `r.entry_price ?? r.entry_px`, `r.current_price`, `r.tp_price`, `r.sl_price`.

For **closed paper trades** (status=closed): show in panel with resolved card style for ~the last few trades. `pnl_usd > 0 → 'won'`, `pnl_usd <= 0 → 'lost'`.

### Change 3 — Move Shadow Feed to drawer tab
- Remove the `sh-stats-grid` + `shadow-feed` div block from the left column HTML entirely
- Add a new `<button class="tab-btn" onclick="switchTab('shadow',this)">Shadow</button>` tab to the drawer, positioned between Trade Log and Candidates
- Add a new `<div id="tab-shadow" class="tab-panel">` containing:
  - The shadow stats bar (sh-stats-grid: Signals / No Trade / Win Rate / P&L units)
  - The shadow feed ticker (compact shadow-ticker-row rows — existing `renderShadowFeed` output)
- Wire `refreshTab('shadow')` to call `fetchShadow()`

### Change 4 — Section header cleanup
- Left column section title: "Active Positions" (remove "(shadow)" subtitle)
- Remove the "Shadow Advisory — Not Executed" subtitle line that appears at top of the shadow section
- The "shadow_label" on individual cards can stay as a small dim indicator per card if it helps distinguish, but shouldn't dominate

---

## What to keep unchanged

- All CSS design tokens, dark theme — do NOT rewrite styles
- `renderGameCard()`, Live Games section, games poll loop
- KPI strip (right column) — can leave as-is or simplify labels but don't break it
- `renderTrades()` in Trade Log tab — unchanged
- `renderCandidates()`, `renderMarkets()`, `renderSignals()` — unchanged
- Manual trade tab — unchanged
- `prob-track-v2` component logic — unchanged
- `buildSparkline()` — unchanged
- Poll interval (10s) — unchanged

---

## Verification steps

1. `python -m sports_bot_v2.dashboard_server` — server starts, no import errors
2. Open `http://localhost:8000`
3. HUD cells labeled: system status | mode | active positions | live P&L
4. Left column has ONE section "Active Positions" — no "Shadow Advisory" section below it
5. Drawer has "Shadow" tab that shows the shadow ticker
6. Position cards have source badges (PAPER-BOT / PAPER-MODEL / MANUAL / SHADOW)
7. No JS console errors on load when APIs return empty data

---

## Rollback

Revert `dashboard.html` only. All changes are front-end rendering. No DB changes, no execution logic changes.
