# PROVISIONAL REVIEW — DASHBOARD_HIERARCHY_FIX_001

Decision: APPROVED_PENDING_CLAUDE

## Outcome

This pass made a real hierarchy/default-state change rather than another cosmetic pass.

## What changed structurally

1. **Trade log is no longer the default focal surface**
   - default active tab is no longer `Trade Log`
   - secondary drawer/tab area defaults to `Shadow`
   - trade history remains secondary and non-default

2. **Live-game-first content now sits above the fold**
   - a dedicated live-games-focus section now appears above the prior secondary surfaces
   - this sits alongside the main live monitor and accounting strip as the initial monitoring context

3. **Default page load now emphasizes live situation, not history**
   - if active positions exist, the user first sees live monitor + focused game/position context
   - if no active positions exist, the live game monitor or intentional empty-state monitor still leads

## Scope check

- No model logic changes
- No strategy changes
- No execution logic changes
- No backend change needed
- No truth regression introduced

## Decision

APPROVED_PENDING_CLAUDE
