# REVIEW_MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001.md

## Verdict
APPROVED

## Decision
Approve `MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001`.

## Why
- Worker stayed within allowed scope.
- Only `dashboard_server.py` was modified.
- Root cause matched the task brief: fallback logic could supersede healthy live stream marks too easily.
- Patch intent is correct: preserve fresh authoritative stream marks and restrict `rest_fallback` to truly missing/stale cases.
- `python -m py_compile dashboard_server.py` passed.

## What was changed
- `dashboard_server.py`
- Fallback gate tightened so REST polling does not override a fresh non-stale stream mark for the same slug.
- Stream marks remain the primary authority when healthy.
- `mark_source` should now better reflect the source actually used for the displayed mark.

## Runtime note
- Restart was completed after this fix.
- A separate read-only verify can still be run later, but the operator's current urgent issues have shifted to confidence-gate failure and side-semantics mismatch.

## Manager judgment
Close this task to DONE.
Do not keep it as the active bottleneck while higher-severity runtime truth issues are unresolved.
