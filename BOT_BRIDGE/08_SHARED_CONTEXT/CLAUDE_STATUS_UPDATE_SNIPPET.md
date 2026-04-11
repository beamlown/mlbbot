# CLAUDE_STATUS_UPDATE_SNIPPET.md

Use this to update `08_SHARED_CONTEXT/CLAUDE_STATUS.md`.

## Replace the dashboard display/issues paragraph with:

- **Display issues — fallback reliability patched, verify pending** — `MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001` was approved after the worker tightened fallback authority in `dashboard_server.py`. Fresh stream marks should now remain primary, with `rest_fallback` limited to truly missing/stale cases. Restart is required. `MARK_SOURCE_FALLBACK_RELIABILITY_VERIFY_001` is now ACTIVE to confirm the fix is live and materially reduces fallback dominance.

## Add under Completed This Reconciliation Pass
| MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001 | APPROVED — `dashboard_server.py` fallback gate tightened so fresh stream marks are not superseded by fallback marks; `py_compile` PASS; restart required. |

## Update Open Items section
Replace the generic dashboard mark-source issue item with:

| **Mark-source fallback verification** | HIGH | Fallback reliability patch is in source, but restart + runtime verification are still required. `MARK_SOURCE_FALLBACK_RELIABILITY_VERIFY_001` ACTIVE. |

## Keep unchanged for now
- Confidence gate remains PARTIALLY ACTIVE
- `BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001` is still required
- user/fill stream credentials remain blocked on Johnny
