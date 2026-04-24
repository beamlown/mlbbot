# PROVISIONAL REVIEW — INCIDENT_PROCESS_DB_001

Decision: CHANGES_REQUESTED_PENDING_CLAUDE

## Scope

Incident debug / containment only. No production code was changed. BOT_BRIDGE files only were written.

## What was verified

1. **Duplicate processes were real**
   - Confirmed two launcher trees / two effective stacks.
   - Confirmed duplicate `bot_core.py`, `dashboard_server.py`, and `resolution_watcher` processes.

2. **Duplicate launcher/process topology was a real live cause**
   - Duplicate bridge opens were observed in the live log during the incident window.
   - Example: `trade=111` and `trade=112` for the same slug and price at the same second.

3. **Containment was safely performed**
   - The duplicate child launcher tree was terminated.
   - Post-containment, only one live stack remained.

4. **insert_open_trade is the actual bridge path in live code**
   - `bot_core.py` bridge path calls `insert_open_trade()`.
   - `core/db.py` currently contains the intended `BEGIN IMMEDIATE` / pre-check logic in source.

## What remains unresolved

1. **Why duplicate writes still succeeded in live behavior**
   - Most likely explanations now narrowed to:
     - duplicate process topology caused the incident, and
     - the expected DB unique protection was missing, failed to create, or was not active in the live DB at the time.

2. **Live DB unique index presence not directly proven**
   - `sqlite3` CLI is unavailable in this environment.
   - Inline Python DB inspection was blocked by tool approval policy in this channel.
   - Therefore, the exact live index/schema state remains unverified.

3. **Open count still shows 4 after containment**
   - This is consistent with duplicate rows already written before containment.
   - Containment stopped the extra stack, but did not clean historical open duplicates.

## Conclusion

This incident is partially contained but not fully closed.

- Process-topology duplication was real.
- Safe containment succeeded.
- Root cause is most likely **duplicate launcher/process topology plus ineffective live DB enforcement at time of write**.
- Additional follow-up is required to confirm the DB index state and clean existing duplicate opens.

## Decision

CHANGES_REQUESTED_PENDING_CLAUDE
