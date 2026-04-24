# HANDOFF_DASHBOARD_REDESIGN_SHELL_001

## Status: HOLD_PENDING_EXECUTION_TRUTH

**Do not begin until:**
1. `EXECUTION_HELD_SIDE_SEMANTICS_001` APPROVED
2. `DASHBOARD_REDESIGN_ARCH_001` APPROVED and `DASHBOARD_REDESIGN_SPEC_001.md` exists

---

## What this task is

Phase 1 of the redesign. **Shell and navigation only — no business logic, no data binding.**

You are implementing the outer skeleton:
- Dark premium layout
- 5-tab navigation bar
- 5 empty tab panel containers (`#tab-live`, `#tab-positions`, `#tab-games`, `#tab-history`, `#tab-system`)
- Persistent command bar (top strip with bankroll, win rate, open count)
- Pure JS tab switching (no page reload)
- CSS design tokens

**Only file you may touch: `dashboard.html`**

---

## What you must NOT do in this phase

- Do not populate tab content with real data (that is phases 2-3)
- Do not delete any existing JS functions (preserve all render functions — they will be rewired later)
- Do not touch `dashboard_server.py`
- Do not change the SSE connection or any data fetch logic

---

## Design tokens to define

```css
--color-bg: #0d0f14 (or similar near-black)
--color-surface: #161920 (card backgrounds)
--color-accent: #00d4ff (cold blue accent)
--color-text: #e8eaf0
--color-muted: #6b7280
--color-positive: #22c55e
--color-negative: #ef4444
```

---

## Tab switching JS pattern

```javascript
function switchTab(name) {
  document.querySelectorAll('.tab-panel').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).style.display = 'block';
  document.querySelector('[data-tab="' + name + '"]').classList.add('active');
}
// Default on load:
switchTab('live');
```

No CSS animations on tab switch. Instant or opacity fade only.

---

## Deliverable check

- [ ] `dashboard.html` loads at `http://localhost:8900` without errors
- [ ] 5 tabs visible and clickable
- [ ] LIVE is active tab on load
- [ ] Command bar visible on all tabs
- [ ] All existing JS render functions still in source (grep: `buildUnifiedPositionCards`, `renderTrades`, `updateState`)
- [ ] `dashboard_server.py` diff is empty
- [ ] No horizontal scroll at 390px
