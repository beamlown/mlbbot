# REVIEW_POSITION_SIDE_SEMANTICS_MERGE_FIX_001.md

## Verdict
APPROVED

## Decision
Approve `POSITION_SIDE_SEMANTICS_MERGE_FIX_001`.

## Why
- Worker stayed within allowed scope.
- Only `dashboard.html` was modified.
- The patch matches the approved audit finding:
  stale cached mark data in `renderUnifiedPositions()` was overwriting current trade semantic identity fields.
- The worker replaced the unsafe full-object spread with a field-specific merge that protects trade identity fields.
- The worker also fixed the secondary Games-tab slug-key mismatch in the same file.
- No restart is required because `dashboard.html` is served statically; a browser hard refresh is sufficient.

## What changed
- `dashboard.html`
- `renderUnifiedPositions()` now merges only explicitly named safe dynamic mark/price/game-state fields from cached mark data
- The current trade object's semantic identity fields remain authoritative and are no longer overwritten by stale cache
- `renderGamesTab()` now normalizes slug keys so open positions can match the Games-tab lookup path

## Protected semantic identity fields
The patch preserves current-trade fields such as:
- `side`
- `backed_team`
- `faded_team`
- `held_contract_side`
- `side_label`
- `entry_px`
- `qty`
- `id`
- and other trade identity fields

## Runtime note
- No server restart required
- Browser hard refresh (`Ctrl+Shift+R`) is required to pick up the new `dashboard.html`

## Manager judgment
Close `POSITION_SIDE_SEMANTICS_MERGE_FIX_001` to DONE.
If `MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001` is still intentionally open, leave it as the only remaining ACTIVE task.
