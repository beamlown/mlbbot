# CLAUDE_STATUS_UPDATE_SNIPPET.md

Use this to update `08_SHARED_CONTEXT/CLAUDE_STATUS.md`.

## Replace the dashboard display issues paragraph with:

- **Display issues — trace complete, fix opened** — `DASHBOARD_MARK_SOURCE_AND_GUARD_MESSAGE_AUDIT_001` and `MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001` cleared the front-end of being the primary cause. `mark REST` is expected rendering when `mark_source='rest_fallback'`. The remaining issue is upstream: fallback marks appear too frequent/inaccurate for operator trust. `MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001` is now ACTIVE to preserve stream mark authority and reduce fallback dominance.

## Add under Completed This Reconciliation Pass
| MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001 | PARTIAL PASS — end-to-end mark_source chain traced; mark REST confirmed as expected fallback chip; no current runtime/dashboard source for hardcoded max-down warning; upstream fallback reliability issue remains. |

## Update Open Items section
Replace the generic dashboard display issues item with:

| **Mark-source fallback reliability** | HIGH | `mark REST` is confirmed fallback behavior, but operator reports fallback is too frequent/inaccurate. `MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001` ACTIVE to keep stream marks primary and harden stale fallback behavior. |

## Keep unchanged for now
- Confidence gate remains PARTIALLY ACTIVE
- `BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001` is still required
- user/fill stream credentials remain blocked on Johnny
