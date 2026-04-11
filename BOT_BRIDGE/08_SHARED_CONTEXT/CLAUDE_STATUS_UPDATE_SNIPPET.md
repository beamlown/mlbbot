# CLAUDE_STATUS_UPDATE_SNIPPET.md

Use this to update `08_SHARED_CONTEXT/CLAUDE_STATUS.md`.

## Add under Completed This Reconciliation Pass
| POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001 | APPROVED — execution truth and server payload mapping clean; root cause traced to dashboard.html client-side full-object merge that lets stale cache overwrite current trade side semantics; secondary Games-tab slug-key mismatch also found. |

## Replace the dashboard display/issues paragraph with:
- **Display issues — side-semantics root cause found, fix active** — `POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001` traced the backed-team mismatch to a stale client-side merge in `dashboard.html`. `POSITION_SIDE_SEMANTICS_MERGE_FIX_001` is now ACTIVE to keep current trade identity fields authoritative and prevent stale cache overwrite.

## Update Open Items section
Replace or add:
| **Side-semantics merge fix** | HIGH | dashboard.html stale cache merge can overwrite current trade side/backed_team/faded_team fields. `POSITION_SIDE_SEMANTICS_MERGE_FIX_001` is now ACTIVE. |

## Keep unchanged for now
- pycache delete + cold restart remains operator-critical
- user/fill stream credentials remain blocked on Johnny
