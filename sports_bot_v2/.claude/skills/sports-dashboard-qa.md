# Skill: Sports Dashboard QA

Manual QA checklist for dashboard changes.

## Mobile layout (375px viewport)
- [ ] No horizontal scrollbar at any point
- [ ] HUD (4 stats) fits in one row — values 13px+ readable
- [ ] Active Positions cards: team name visible, prob bar renders, badges don't overflow
- [ ] Shadow Feed stats: 2-col grid on <480px, 4-col on wider
- [ ] Live Games: single column, score numbers large and readable
- [ ] KPI strip: 2-col on <480px, 3-col on mobile, 6-col on desktop
- [ ] Tab bar: horizontally scrollable, no wrapping, 44px height
- [ ] Tab panels: max-height with overflow-y scroll
- [ ] Manual trade form: 3-col input row doesn't overflow (grid-template-columns:1fr 80px 70px)
- [ ] All buttons min-height 44px

## Data rendering
- [ ] Active Positions count (section-count badge) matches number of rendered cards
- [ ] KPI "Open" count matches Bot Open Positions list in Manual tab
- [ ] Shadow P&L HUD matches sh-pnl-val in feed stats bar
- [ ] HUD "Active" = unresolved recs, "Resolved" = matched recs
- [ ] Game cards: live games show situation bar (diamond + count dots), final/scheduled show only score
- [ ] Probability bar fills sum to ~100% (yesFill + noFill = 100)
- [ ] Confidence bar width = confPct%
- [ ] TP = 85¢, SL = entry × 0.80 (approximate)
- [ ] New position cards animate in (slideIn class applied on first render)

## Polling
- [ ] Exactly one `setInterval(poll, 10000)` in the JS
- [ ] `last-refresh` timestamp updates every 10s
- [ ] Shadow fetch runs every poll cycle
- [ ] Bankroll fetch runs every 3rd poll cycle

## State consistency
- [ ] Open position count in KPI equals renderBotPositions() card count
- [ ] Both use the same normalized `positions` array from `renderState()`
- [ ] No duplicate `renderState` or `fetchState` definitions

## Desktop layout (≥800px)
- [ ] Two-column grid: left col 420px, right fills
- [ ] Drawer visible by default (display:block !important)
- [ ] KPI strip shows 6 columns
- [ ] Shadow stats grid shows 4 columns
- [ ] Mob menu button hidden
