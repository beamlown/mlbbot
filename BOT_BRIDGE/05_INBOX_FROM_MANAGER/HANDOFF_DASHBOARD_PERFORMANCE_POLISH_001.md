# HANDOFF_DASHBOARD_PERFORMANCE_POLISH_001

## Status: HOLD_PENDING_EXECUTION_TRUTH

**Do not begin until:** `DASHBOARD_POSITIONS_HISTORY_SYSTEM_001` APPROVED.

---

## What this task is

Phase 4 of the redesign. **Performance and flicker elimination only. No new features. No truth-model changes.**

Allowed file: `dashboard.html` only. Do NOT touch `dashboard_server.py`.

---

## Problems to fix

| Problem | Fix |
|---|---|
| Full card re-render on every poll | Convert to in-place DOM update — compare current value before writing |
| Full table rebuild on every trades poll | Diff by trade ID — only update changed rows, insert new rows |
| CSS transitions on numeric values | Remove all `transition:` from `.stat-val`, price, PnL elements |
| Layout shift when price updates | Add `min-height` to card containers |
| Tab-switch flash | Confirm `display:none/block` pattern, not DOM removal |
| Blank page on load | Add skeleton/loading states for game monitor, position cards, account strip |
| Console.log in production | Audit and remove all |

---

## Explicit non-changes

You must NOT change:
- Any pricing formula (`unrealizedPct`, `currentHeldPrice`, `bid_yes`, `bid_no`)
- Any API endpoint or poll interval (unless it is proven to cause flicker)
- The SSE connection or update handler logic (only the DOM write path within it)
- What data is shown — only how it is rendered
- `dashboard_server.py`

---

## Verification of non-changes

After this phase, the manager will grep for:
```
grep -n "unrealized\|current_held\|bid_yes\|bid_no\|entry_px" dashboard.html
```
The formulas must be identical to what existed before this phase.

---

## Deliverable check

- [ ] Position cards update in-place on SSE tick (no card list re-render)
- [ ] Trade history diffs by ID (no table rebuild on every poll)
- [ ] No CSS transitions on numeric elements
- [ ] No layout shift on price update
- [ ] Tab switching has no white flash
- [ ] Loading states appear on page load before first data
- [ ] No console.log in production paths
- [ ] Pricing formulas unchanged — confirmed by grep
- [ ] `dashboard_server.py` diff is empty
