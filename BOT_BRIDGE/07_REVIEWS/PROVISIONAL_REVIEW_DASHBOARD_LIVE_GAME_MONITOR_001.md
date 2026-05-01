# PROVISIONAL REVIEW — DASHBOARD_LIVE_GAME_MONITOR_001

Decision: APPROVED_PENDING_CLAUDE

## Outcome

This task was implemented within the requested narrow scope and meaningfully improves live monitoring clarity without truth regression.

## What improved

1. **Main monitoring object is now correct**
   - The primary object is effectively a hybrid live game + active position card.
   - The view is centered on real executed paper positions, not on historical log rows.

2. **Side / price / PnL / accounting are clearer**
   - exact side is clearer
   - entry/current relationship is clearer
   - committed capital and live equity are surfaced
   - available cash vs capital in trades is clearer

3. **Trade log no longer dominates**
   - it remains present, but secondary
   - the user no longer has to hunt through log-first layout to understand the live situation

4. **Live game focus improved without lying**
   - cards keep game context visible
   - current market/position values are presented as monitoring values, not fabricated real-time streams

## Backend scope check

A tiny backend addition was appropriate and bounded:
- added bankroll/accounting fields derived from live open trades
- no trading logic changed
- no execution logic changed

## Truth-model check

- Main positions still come from real paper trades
- Shadow remains diagnostics only
- No count/source regression was introduced

## Decision

APPROVED_PENDING_CLAUDE
