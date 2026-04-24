# HANDOFF — INCIDENT_DB_REMEDIATION_001
## Remediate duplicate open rows and enforce unique open-slug index in live DB

---

## STATUS: ACTIVE

This is a narrow DB remediation task.
No production code changes.
No dashboard/UI changes.
No strategy/model changes.

---

## Required safeguards before any DB write

1. Pause/stop the remaining entry writer first
2. Create a timestamped backup of:
   - `C:\Users\johnny\Desktop\sports_bot_v2\trades_sports.db`
3. If backup fails, stop and return BLOCKED

---

## Approved cleanup rule

For duplicate open rows with the same `market_slug`:
- KEEP the earliest open row (lowest id / earliest ts_open)
- CLOSE/VOID extra rows with:
  - `status='closed'`
  - `ts_close=<remediation timestamp>`
  - `exit_px=entry_px`
  - `pnl_usd=0.0`
  - `fees_usd=0.0` if writable/available
  - `reason_close='duplicate_remediation_void'`
- preserve source, row ids, ts_open, and original entry fields
- do not delete rows

After duplicate open rows are remediated:
- create the missing unique index:
  - `idx_trades_one_open_per_slug`

---

## Required verification afterward

1. DB backup exists
2. no duplicate open rows remain for same slug
3. unique index exists
4. `/api/state` open count matches DB open rows
5. no new duplicate opens appear in the verification window
6. single live stack remains intact

If any step is unsafe or fails, stop and return BLOCKED with exact reason.
