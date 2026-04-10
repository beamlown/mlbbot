# HANDOFF — DASHBOARD_HIERARCHY_FIX_001
## Make dashboard genuinely live-game-first and demote trade log from default focus

---

## STATUS: ACTIVE

This is a narrow but real layout hierarchy fix.
Do not solve it with cosmetic tweaks alone.
Do not just tweak labels, colors, spacing, or headings.
Actually change what dominates the screen and the default active surface.

---

## Required structural changes

1. The primary above-the-fold section must be the live game / active position monitor.
2. The trade log must NOT dominate the initial viewport.
3. The trade log should be secondary:
   - collapsed by default
   - moved lower
   - or placed in a secondary tab/drawer/section
4. If there is a live game with an active position, that game/position card should be the main focal point.
5. If there are multiple live positions, they should appear as the main monitoring cards.
6. Background diagnostics and trade history must feel secondary immediately.

---

## Extra requirement

The trade log must NOT be the default active surface on page load.

Default page load should emphasize:
- live game + active position monitor
- not trade history

Secondary drawer/tab area should start in a collapsed or visually quiet state.

If there are no active live positions, the page should still prioritize:
- live game monitoring
- or a clean monitor empty state
- not the trade log

---

## Acceptance criteria

1. trade log no longer owns the page
2. live game / active position monitor is the primary above-the-fold content
3. user can immediately see the current live situation
4. shadow/debug/history remain secondary
5. no truth regression
6. no broad redesign drift
