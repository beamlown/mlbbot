# PROVISIONAL REVIEW — DASHBOARD_POLISH_001

Decision: APPROVED_PENDING_CLAUDE

## Outcome

This polish/tightening task is complete and appropriately scoped.

## What improved

1. **Canonical count ownership is now singular**
   - `kpi-open`, `cmd-open`, and the main positions count now derive from the same canonical `openPaperPositions` array.
   - The prior timing-sensitive split ownership between `renderState()` and `renderUnifiedPositions()` for these counts was removed.

2. **Main cards are easier to scan**
   - matchup context is clearer
   - source is clearer
   - stale current-price situations are explicit instead of implied
   - the main card remains centered on real execution truth

3. **Shadow stays secondary**
   - no promotion of shadow-only entries into main position exposure
   - diagnostics remain in their background role

4. **0-open state is now intentional**
   - clearly communicates that there are no live paper positions
   - does not imply advisory entries are active exposure

## Scope check

- No model logic changes
- No execution logic changes
- No backend addition required
- No truth regression observed from the intended code-path changes

## Decision

APPROVED_PENDING_CLAUDE
