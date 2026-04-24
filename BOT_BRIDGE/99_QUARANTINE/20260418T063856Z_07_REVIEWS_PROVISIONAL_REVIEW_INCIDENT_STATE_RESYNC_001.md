# PROVISIONAL REVIEW — INCIDENT_STATE_RESYNC_001

Decision: BLOCKED_PENDING_CLAUDE

## What passed

1. **State truth converged**
   - DB open rows: `0`
   - `/api/state` open positions: `0`
   - `/api/trades` recent open count observed: `0`

2. **Duplicate open behavior did not reappear in the short observation window**
   - No new duplicate pair was observed after resync.

3. **Only one bot_core writer appears active**
   - The resynced stack has a single active `bot_core` writer.

## What failed

1. **Topology is not yet cleanly canonical**
   - There are still duplicated non-writer services:
     - `recommendation_api`
     - `dashboard_server`
     - `resolution_watcher`
   - One set runs under the older parent tree.
   - Another set runs under the newly started launcher tree.

2. **Canonical tree selection is unresolved**
   - To finish stabilization, one full service tree must be designated canonical and the other stopped.
   - That is an operational selection step, not a safe inference to make silently.

## Conclusion

This task achieved partial stabilization:
- truth alignment is restored
- duplicate open rows are gone
- no fresh duplicate opens were observed in the short window

But the process topology is still duplicated for non-writer services, so the system should not yet be declared fully stable enough to return to normal dashboard truth work.

## Required next step

Issue a narrow ops decision/task specifying which full service tree is authoritative, then stop the non-canonical tree and re-verify:
- one launcher stack only
- one recommendation_api only
- one dashboard_server only
- one resolution_watcher only
- one bot_core only

## Decision

BLOCKED_PENDING_CLAUDE
