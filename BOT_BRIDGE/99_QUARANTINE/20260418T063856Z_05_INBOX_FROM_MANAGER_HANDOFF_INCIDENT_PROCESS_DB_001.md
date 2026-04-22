# HANDOFF — INCIDENT_PROCESS_DB_001
## Incident debug / containment — duplicate process topology and DB enforcement

---

## STATUS: ACTIVE

This is incident debug / containment only.

Do not redesign anything.
Do not retrain anything.
Do not touch dashboard UI.
Do not change strategy.
Do not widen scope.
Do not change production code unless exact minimal fix is proven necessary. If code change is required, stop and report BLOCKED with exact files needed.

BOT_BRIDGE files are the only allowed writes unless the task becomes BLOCKED.

---

## Phase 1 — containment

1. Capture evidence first:
   - running relevant Python processes with PIDs and command lines
   - current `/api/state`
   - current `/api/trades` if available
   - latest relevant bot / bridge / launcher logs
2. Identify duplicate stack processes.
3. Report the exact intended single valid process topology.
4. If safe, stop duplicate extra stack processes so only one valid stack remains.
5. Preserve logs and evidence.

---

## Phase 2 — root-cause debug

Determine which is the true failure:
1. duplicate launcher/process topology
2. multiple runtime/DB paths in use
3. DB unique index missing or not created
4. bridge path not actually using `insert_open_trade()`
5. unique insert protection bypassed
6. working-directory/path mismatch
7. some combination

You must verify:
- exact DB file path each active bot process is using
- whether the trades table has the expected unique open-slug protection index
- whether `insert_open_trade()` is the actual path used for bridge-created trades
- whether `launch_all.py` is responsible for duplicate spawning
- whether `bot_core.py` instances are tied to one launcher or multiple launchers

---

## Deliverables

Write:
- `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_INCIDENT_PROCESS_DB_001.json`
- `C:\Users\johnny\Desktop\BOT_BRIDGE\07_REVIEWS\PROVISIONAL_REVIEW_INCIDENT_PROCESS_DB_001.md`

The provisional review must clearly end with one of:
- `APPROVED_PENDING_CLAUDE`
- `CHANGES_REQUESTED_PENDING_CLAUDE`
- `BLOCKED_PENDING_CLAUDE`
