# PROVISIONAL REVIEW — VERIFY_DASHBOARD_TRUTH_002

Decision: APPROVED_PENDING_CLAUDE

## Outcome

The dashboard truth fix holds in live behavior for the core requirement:
- main positions are sourced from real open paper trades only
- shadow-only advisories are not rendered as main position cards
- live PnL for real positions is based on actual execution basis, not shadow fixed-size estimates

## What was verified

1. **Main cards use real paper truth**
   - `dashboard.html` builds `openPaperPositions` from `/api/trades` open paper trades only.
   - Main cards render from that array.

2. **Shadow is diagnostics only**
   - `/api/mlb-shadow` still exposes many advisory entries.
   - Those entries are shown in Shadow diagnostics/background areas, not as main position cards.

3. **Live truth held in current snapshot**
   - `/api/trades` open count: `1`
   - `/api/state` open positions count: `1`
   - This matched cleanly in the observed live snapshot.

4. **Real live PnL basis is correct**
   - Paper-card PnL logic uses actual `qty`, `entry_px`, and `current_price`.

5. **Stale current price behavior is explicit**
   - When no current price is available, the card labels the stat as `Current (stale)`.

## Minor remaining issue

There is still a small ownership/timing imperfection:
- `renderState()` writes `kpi-open` and `cmd-open` from `/api/state`
- `renderUnifiedPositions()` then overwrites those from `openPaperPositions`

In the live snapshot this did not create a mismatch because both sources matched.
This is a minor polish/tightening issue, not a hard truth-layer failure.

## Conclusion

The system is ready to move from truth-fix work into usability polish / coherence tightening.

## Decision

APPROVED_PENDING_CLAUDE
