# HANDOFF — DASHBOARD_STYLE_FUN_001
## Style / UX polish for dashboard command-center feel without truth regression

---

## STATUS: ACTIVE

This is style / UX polish only.

Do not touch model logic.
Do not touch execution logic.
Do not re-open incident work.
Do not break the current dashboard truth layer.

The stabilized truth layer must remain intact:
- main positions truth already comes from real paper trades
- shadow/advisory stays background-only
- counts/KPIs are already stabilized

---

## Main goal

Make the dashboard feel more fun, polished, and easier to enjoy using while preserving the current truth model.

---

## Priority 1 — Active positions should feel premium

Improve the main active position cards so they are easier and more satisfying to read.

Emphasize:
- side
- matchup
- entry price
- current price
- live PnL
- TP
- SL
- source
- real lifecycle status

Desired feel:
- easier to scan
- stronger hierarchy
- cleaner spacing
- more visually rewarding
- still truthful

---

## Priority 2 — Command-center hierarchy

Improve the top-level page so the user can understand the current state quickly.

The page should clearly communicate:
- overall system health
- active positions
- whether there are any live paper trades
- current execution context
- background diagnostics tucked away

---

## Priority 3 — Shadow/debug containment

Keep shadow/advisory/candidate/debug information available, but make it feel secondary.
Do not let it visually compete with live executed positions.

---

## Priority 4 — Empty state polish

When there are no live paper positions:
- make the page still feel intentional and good
- no awkward dead space
- no misleading sense that advisory items are active trades

---

## Priority 5 — Mobile-friendly polish

Without redesigning the app architecture, improve:
- spacing
- readability
- visual grouping
- touch-friendliness
- card readability on phone screens

---

## Constraints

- preserve the current truth model
- do not make shadow feel like live exposure
- do not invent data
- do not change backend behavior unless a tiny frontend-supporting field addition is absolutely necessary
- prefer keeping this to `dashboard.html` only

---

## Acceptance criteria

1. main active positions are more visually clear and enjoyable
2. page hierarchy is easier to understand at a glance
3. shadow/debug areas feel secondary
4. empty state feels intentional
5. mobile readability is improved
6. no truth regression
7. no count/source regression
