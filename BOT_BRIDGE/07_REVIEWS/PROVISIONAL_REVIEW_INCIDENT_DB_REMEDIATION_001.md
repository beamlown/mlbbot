# PROVISIONAL REVIEW — INCIDENT_DB_REMEDIATION_001

Decision: CHANGES_REQUESTED_PENDING_CLAUDE

## What succeeded

1. **Backup safeguard passed**
   - Backup created before remediation:
     - `C:\Users\johnny\Desktop\BOT_BRIDGE\09_ARCHIVE\trades_sports_pre_remediation_20260405_191246.db`

2. **Duplicate open rows were remediated under the approved rule**
   - Kept earliest row:
     - `id=101`
   - Voided duplicate extra row:
     - `id=102`
   - Void method preserved auditability:
     - row retained
     - status changed to `closed`
     - `reason_close='duplicate_remediation_void'`
     - zero PnL / zero fees / exit at entry

3. **Unique open-slug protection index now exists**
   - `idx_trades_one_open_per_slug`
   - Verified present in live DB after remediation

4. **No duplicate open rows remain in DB after remediation**
   - DB open rows now reduced to 2
   - duplicate open group count after remediation = 0

5. **No new duplicate pair was observed in the short post-fix verification window**
   - one new single `BRIDGE OPEN trade=113` was observed
   - no paired duplicate open for that event was seen

## What still needs follow-up

1. **/api/state alignment not yet cleanly proven**
   - DB open rows after remediation = 2
   - `/api/state` still reported open=3 in the short verification window
   - state was stale during verification

2. **Single live stack topology is not yet cleanly restored**
   - The duplicate writer was stopped for remediation.
   - A bot_core process was restarted for verification, but the resulting process tree is not yet a clean canonical launcher topology.
   - This means supervision/process topology still needs an ops follow-up check.

## Conclusion

The DB remediation itself succeeded.

- duplicate open rows were remediated
- unique index now exists
- no duplicate open rows remain in the DB
- no fresh duplicate pair was observed in the short verification window

However, the runtime/state alignment and clean single-stack supervision are not fully closed yet.

## Decision

CHANGES_REQUESTED_PENDING_CLAUDE
