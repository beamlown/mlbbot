# Worker Handoff Note — PATCH_2026-04-18-V1_RESTART_VERIFY_001
## Created: 2026-04-18

**Title**: Restart bots for patch 2026-04-18-v1 and verify new runtime is live
**Priority**: HIGH
**Subsystem**: runtime / launcher
**Assigned**: SONNET_WORKER
**Depends on**: AUDIT_2026-04-18-v1.md → DECISION: SHIP

---

## What this task is

Patch 2026-04-18-v1 has been audited SHIP. The patch contains only documentation (BOT_BRIDGE_OPERATING_PRINCIPLES.md, rules updates) and read-only verifications — no production code changed. Therefore the runtime `config_hash` is expected to be **unchanged** (`f87077f219dd`) after restart.

This task does three things:
1. Cleanly stop the running bot process.
2. Start a fresh instance via the canonical launcher.
3. Emit a startup-proof block confirming the new PID, `config_hash`, and gate env values match expectation.

This is a live-verification task. If `config_hash` diverges from `f87077f219dd`, STOP and report — do not paper over a surprise hash change.

---

## Preconditions (must check and log before any action)

- Single running instance: exactly one `python bot_core.py` process. If 0 or >1, report and HALT.
- Record current PID and start time before killing.
- Read `runtime/state.json` and record: `config_hash`, `loop_count`, `session_start_ts`, any open trades (`len(open_trades)`).
- Confirm no pending trade execution in the last 30s of the launcher log. If a trade is mid-flight, HALT and re-queue.

---

## Restart procedure

1. Stop the current bot cleanly. Prefer the launcher's stop path; fall back to `taskkill /PID <pid>` (not /F unless clean stop fails after 15s).
2. Wait for PID to disappear and for `runtime/bot.pid` to be removed or staled.
3. Start via the canonical launcher only (no manual `python bot_core.py` invocation).
4. Wait up to 30s for the new process to emit its STARTUP_PROOF log line.

---

## Acceptance criteria (all must pass)

- New PID is different from the old PID. ✓
- STARTUP_PROOF log line contains: `MIN_ENTRY_CONFIDENCE=0.65`, `MIN_ENTRY_PRICE=0.22`, `LATE_INNING_BLOCK=7`, `config_hash=f87077f219dd`. ✓
- `runtime/state.json` post-restart: `config_hash=f87077f219dd` (unchanged — patch was doc-only). ✓
- Only one `bot_core.py` process exists after restart. ✓
- `loop_count` post-restart starts at 0 or 1 and increments on subsequent reads. ✓
- No `confidence_too_low:...:<anything other than 0.650>` threshold appears in the new process's log.

If **any** criterion fails, report with raw log excerpts and HALT. Do not attempt a second restart without manager approval.

---

## Do not do

- Do not edit any source file (this is a pure runtime task).
- Do not modify `runtime/state.json`, `runtime/bot.pid`, `paper_trades.db`, or any file under `runtime/`.
- Do not launch via `python bot_core.py` directly — use the canonical launcher.
- Do not suppress or rotate the launcher log during the restart window.

---

## Deliver back

Write `BOT_BRIDGE/06_OUTBOX_FROM_WORKER/RESULT_PATCH_2026-04-18-V1_RESTART_VERIFY_001.json` with:

```json
{
  "old_pid": "<int>",
  "new_pid": "<int>",
  "stop_method": "launcher|taskkill|taskkill_force",
  "startup_proof_line": "<exact log line>",
  "config_hash_pre": "<hash>",
  "config_hash_post": "<hash>",
  "expected_config_hash": "f87077f219dd",
  "hash_match": true,
  "gate_values": {
    "MIN_ENTRY_CONFIDENCE": 0.65,
    "MIN_ENTRY_PRICE": 0.22,
    "LATE_INNING_BLOCK": 7
  },
  "open_trades_pre": "<int>",
  "open_trades_post": "<int>",
  "single_process_confirmed": true,
  "halted": false,
  "halt_reason": null,
  "files_read": [],
  "files_changed": []
}
```

Also append a one-line status to `08_SHARED_CONTEXT/CLAUDE_STATUS.md`:
`PATCH 2026-04-18-v1 RESTARTED — pid=<new_pid> hash=<hash> proof=OK`
