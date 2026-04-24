# HANDOFF — INCIDENT_DB_VERIFY_001
## Incident DB verification — live DB path, index state, duplicate open rows, post-containment behavior

---

## STATUS: ACTIVE

This is verification-only first, cleanup second only if verification proves it is safe.

Do not change production code.
Preserve evidence.
If direct DB inspection requires a helper script, create a visible, non-obfuscated, read-only script and use it.

---

## What must be verified

1. exact live DB file path in use by the remaining active stack
2. whether the `trades` table has the expected unique open-slug protection index
3. whether duplicate open rows currently exist for the same `market_slug`
4. whether those duplicate rows are still actually open or should already be resolved/closed
5. whether the current remaining live stack is still writing new duplicates after containment

---

## Constraints

- verification first
- cleanup only if explicitly proven safe
- no production code changes
- preserve evidence
- BOT_BRIDGE files are the intended write targets, plus a visible read-only helper script only if required for DB inspection

---

## Deliverables

Write:
- `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_INCIDENT_DB_VERIFY_001.json`
- `C:\Users\johnny\Desktop\BOT_BRIDGE\07_REVIEWS\PROVISIONAL_REVIEW_INCIDENT_DB_VERIFY_001.md`

The provisional review must clearly end with one of:
- `APPROVED_PENDING_CLAUDE`
- `CHANGES_REQUESTED_PENDING_CLAUDE`
- `BLOCKED_PENDING_CLAUDE`
