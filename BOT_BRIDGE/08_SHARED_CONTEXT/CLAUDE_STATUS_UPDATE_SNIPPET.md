# CLAUDE_STATUS_UPDATE_SNIPPET.md

Use this to update `08_SHARED_CONTEXT/CLAUDE_STATUS.md`.

## Add under Completed This Reconciliation Pass
| POSITION_SIDE_SEMANTICS_MERGE_FIX_001 | APPROVED — `dashboard.html` now uses a field-specific safe merge so stale cached mark data cannot overwrite current trade side/backed_team/faded_team semantics; Games-tab slug-key mismatch also fixed. No restart required; browser hard refresh required. |

## Replace the dashboard display/issues paragraph with:
- **Display issues — side-semantics fix complete** — `POSITION_SIDE_SEMANTICS_MERGE_FIX_001` is approved. The client-side merge in `dashboard.html` now protects semantic identity fields from stale cache overwrite, and the Games-tab slug key mismatch has been fixed. Browser hard refresh is required to pick up the patch.

## Update Open Items section
Replace or add:
| **Mark fallback / guard payload trace** | MEDIUM | Still open only if manager wants the remaining read-only trace completed/closed. Does not block the side-semantics fix. |

## Keep unchanged for now
- pycache delete + cold restart remains operator-critical for bot_core-backed fixes
- user/fill stream credentials remain blocked on Johnny
