# REVIEW_POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001.md

## Verdict
APPROVED

## Decision
Approve `POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001`.

## Why
- The worker stayed read-only and within task scope.
- The worker traced one current live trade end-to-end.
- Execution truth and server-side payload mapping were ruled out cleanly.
- The audit identified a precise client-side root cause in `dashboard.html`:
  `renderUnifiedPositions()` performs a full-object spread merge from cached mark data, allowing stale fields like `side`, `backed_team`, and `faded_team` from an older trade on the same slug to overwrite the current trade's correct semantics.
- The audit also found a secondary Games-tab slug-key mismatch.

## Primary root cause
`dashboard.html` line 1139-style merge:
`latestOpenPaperPositions = openPaperPositions.map(p => ({ ...p, ...(markMap.get(p.market_slug) || {}) }));`

When a trade closes and a new trade opens on the same slug with a different side, stale cached fields from `markMap` overwrite the new trade's correct side semantics. This is a client-side merge bug, not an execution-truth bug.

## Secondary finding
Games-tab open-position lookup is keyed inconsistently:
- stored key includes date slug
- lookup key omits date
This causes positions not to appear correctly in the Games tab.

## Manager judgment
Open a new fix task:

`POSITION_SIDE_SEMANTICS_MERGE_FIX_001`

This should be a tight `dashboard.html` fix only:
- replace the full-object spread with a field-specific merge
- copy only mark/price/game-state fields from stale cache
- never overwrite semantic identity fields like:
  - `side`
  - `backed_team`
  - `faded_team`
  - `entry_px`
  - `qty`
  - `id`
- also fix the Games-tab slug key mismatch if it is in the same file and can be fixed safely within the same patch

## Priority
Promote this to ACTIVE now. The critical risk and session-accounting fixes have already been staged, so this is now the correct next dashboard truth fix.
