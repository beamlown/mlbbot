# REVIEW_DASH_010

Decision: APPROVED

## What passed

- **Scope**: only `dashboard.html` modified — matches allowed_files exactly. No server files touched.
- **Fix A — section title**: line 351 reads `<span class="section-title">Positions</span>` ✅
- **Fix B — badge count**: line 804 reads `$('pos-count').textContent = enriched.length + shadowOnly.length;` ✅ — correctly excludes `resolvedPaper` from the count while still rendering all unified cards.
- **Sequencing**: worker correctly waited for `REVIEW_DASH_009.md` Decision: APPROVED before starting.
- **Rollback**: `dashboard.html` only — revertable.

## What failed

- None.

## Notes

- With current state (0 open, 0 shadow, 2 resolved), badge will now show 0 — matching `cmd-open`. The contradiction between "Active Positions: 2" and "Open: 0" is resolved.
- Resolved cards still render below the (now-accurate) badge count.

## Next action

Board is idle — no queued tasks. Manager should assess next priority.
