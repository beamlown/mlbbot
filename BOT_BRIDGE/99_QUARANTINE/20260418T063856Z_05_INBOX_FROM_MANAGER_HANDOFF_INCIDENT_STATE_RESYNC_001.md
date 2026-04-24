# HANDOFF — INCIDENT_STATE_RESYNC_001
## Restore canonical launcher topology and resync runtime/API state to DB truth

---

## STATUS: ACTIVE

This is process/state stabilization only.

Do NOT change trading logic.
Do NOT change dashboard UI.
Do NOT redesign anything.
No production code changes unless absolutely necessary. If a code fix is required, stop and return BLOCKED with exact files needed.

---

## Priority order

1. restore one clean canonical launcher/process topology
2. verify only one valid instance of each critical service remains
3. make runtime/API state converge to DB truth
4. verify no new duplicate opens appear in the observation window
5. only if code change is absolutely required, stop and return BLOCKED with exact files needed

---

## What to verify

- one launcher stack only
- one bot_core writer only
- one dashboard_server only
- one resolution_watcher only
- one recommendation_api only
- DB open rows count
- `/api/state` open positions count
- `/api/trades` open count if available
- all should align
- no new duplicate opens
- no capacity breach
- no duplicate process respawn

---

## Deliverables

Write:
- `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_INCIDENT_STATE_RESYNC_001.json`
- `C:\Users\johnny\Desktop\BOT_BRIDGE\07_REVIEWS\PROVISIONAL_REVIEW_INCIDENT_STATE_RESYNC_001.md`

The provisional review must end with one of:
- `APPROVED_PENDING_CLAUDE`
- `CHANGES_REQUESTED_PENDING_CLAUDE`
- `BLOCKED_PENDING_CLAUDE`
