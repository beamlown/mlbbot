# HANDOFF — VERIFY_DUPLICATE_ENTRY_001
## Verify duplicate-entry fix in live behavior

---

## STATUS: ACTIVE (verification only)

This is a verification/debug task only.

Do **not** change production code.
If verification proves a hard remaining bug that would require a code change, stop and report:
- `BLOCKED`
- what failed
- what evidence proves it

Only BOT_BRIDGE task/result/review files may be written.

---

## Goal

Prove whether `DUPLICATE_ENTRY_FIX_001` actually solved duplicate open trade creation in live behavior.

---

## What must be verified

1. No duplicate open paper trades for the same `market_slug`
2. No capacity breach like `4/3`
3. Duplicate attempts are logged as skipped instead of creating positions
4. `/api/trades` open count matches true backend open DB rows
5. `/api/state` open positions count matches backend truth
6. Dashboard-facing APIs no longer reflect duplicate real positions caused by backend duplicate opens

---

## Evidence to inspect

- backend DB open trades
- `runtime/state.json`
- `http://127.0.0.1:8900/api/trades`
- `http://127.0.0.1:8900/api/state`
- relevant logs for:
  - `OPEN SKIPPED (duplicate slug)`
  - `BRIDGE OPEN SKIPPED (duplicate slug)`
  - duplicate `OPEN trade=` or `BRIDGE OPEN trade=` lines for same slug close together
  - capacity breaches such as `4/3`, `10/3`, `11/3`, `CAP HIT 4/3`, etc.

---

## Deliverables

Write:
- `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_VERIFY_DUPLICATE_ENTRY_001.json`
- `C:\Users\johnny\Desktop\BOT_BRIDGE\07_REVIEWS\PROVISIONAL_REVIEW_VERIFY_DUPLICATE_ENTRY_001.md`

The provisional review must end with exactly one of:
- `APPROVED_PENDING_CLAUDE`
- `CHANGES_REQUESTED_PENDING_CLAUDE`
- `BLOCKED_PENDING_CLAUDE`
