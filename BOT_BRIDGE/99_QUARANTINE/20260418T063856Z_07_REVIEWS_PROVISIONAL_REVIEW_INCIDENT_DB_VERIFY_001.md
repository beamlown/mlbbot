# PROVISIONAL REVIEW — INCIDENT_DB_VERIFY_001

Decision: CHANGES_REQUESTED_PENDING_CLAUDE

## Scope

Verification-only task. No production code changes were made. No cleanup was performed.

## What was proven

1. **Exact live DB path**
   - Verified as:
     - `C:\Users\johnny\Desktop\sports_bot_v2\trades_sports.db`

2. **Unique open-slug index state**
   - The expected unique index does **not** exist in the live DB schema:
     - expected: `idx_trades_one_open_per_slug`
     - actual: absent

3. **Duplicate open rows still exist**
   - Verified duplicate open rows for:
     - `mlb-stl-det-2026-04-05`
   - Open duplicate ids:
     - `101`
     - `102`

4. **Those duplicate rows are still open**
   - They remain `status='open'`
   - No recent closed rows were found for that slug in the DB inspection output

5. **Post-containment duplicate behavior**
   - No new duplicate pair was directly observed in this verification window after containment
   - However, the verification window is limited and not long enough to claim final safety

6. **State/API truth drift remains**
   - DB currently shows **3 open rows**
   - `/api/state` currently shows **2 open positions**
   - Therefore backend truth and state/API truth are still not fully aligned

## Conclusion

The incident is not fully resolved.

- The live DB path is now proven.
- The unique open-slug protection index is missing in the live DB.
- Duplicate open rows still exist.
- Cleanup may be warranted, but should happen only under a dedicated approved cleanup rule.

## Recommendation

1. Issue a narrow follow-up remediation task to:
   - define the exact safe duplicate-row cleanup rule
   - repair existing duplicate open rows
2. Issue a follow-up fix/ops task to ensure the missing live DB index is actually created in the production DB schema
3. Re-verify after cleanup and schema enforcement

## Decision

CHANGES_REQUESTED_PENDING_CLAUDE
