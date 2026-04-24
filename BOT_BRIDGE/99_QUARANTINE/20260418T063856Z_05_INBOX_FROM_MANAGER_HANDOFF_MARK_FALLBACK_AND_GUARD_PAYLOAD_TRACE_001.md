# HANDOFF — MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001
**Priority:** MEDIUM
**Type:** Read-only trace
**Issued:** 2026-04-10
**Scope:** NARROW — mark_source production chain and guard/warning payload origin only. Do not sweep the repo.

---

## One-sentence task

Trace exactly where `mark_source` is produced and why it resolves to `rest_fallback`, and trace exactly where the guard/warning text shown on the dashboard originates before it reaches the UI.

---

## Context for the worker

The prior task (DASHBOARD_MARK_SOURCE_AND_GUARD_MESSAGE_AUDIT_001) cleared the dashboard layer:

- `dashboard.html` is not generating any "max down" text — it renders raw values from `state.last_guard_result` / `state.guard`
- `dashboard_server.py` is correctly mapping `mark_source` from state hub marks and emitting `rest_fallback` when stale REST polling refreshes a mark
- `runtime/state.json` had null guard fields at audit time

**What remains unresolved:**

**Symptom 1 — mark REST frequency/severity:**
The `rest_fallback` mechanism is confirmed to exist, but it is unknown whether fallback is firing rarely (normal), frequently (degraded stream), or effectively acting as the main mark source for live positions. The live SSE sample showed `mlb-wsh-mil-2026-04-10` already on `rest_fallback`. With the bot at 3/3 capacity (trades 223, 237, 238), if all 3 positions are on `rest_fallback`, the stream may not be delivering price updates for any open positions.

**Symptom 2 — "max down" / guard warning text origin:**
The operator saw a "max down" style warning message. The dashboard renders whatever is in `state.last_guard_result` or `state.guard`. That field was null at audit time, so either: (a) the message was transient and is now gone, (b) the field is written by bot_core loop logic and was stale/cleared after a restart, or (c) it comes from a different upstream field than `last_guard_result`. The exact production code has not been traced.

**Known system state at time of task:**
- 3 open positions (trades 223, 237, 238)
- Bot at MAX_CONCURRENT_TRADES (3/3) — BRIDGE SKIP on every loop
- Most recent restart: 2026-04-10 18:41:26 CDT (post CONFIDENCE_GATE_POSTFIX_VERIFY_001)
- `mark_source='rest_fallback'` confirmed in live SSE payload for at least 1 position
- Guard fields null in last `state.json` read

---

## What you must NOT do

- Edit any code
- Edit `.env`
- Restart any process
- Write to any DB
- Do a broad repo sweep
- Read bot_core.py unless strictly necessary to trace the guard payload write path (justify explicitly)
- Read unrelated model/strategy files

---

## Where to look, in order

### Step 1 — Read current runtime state
```
C:\Users\johnny\Desktop\sports_bot_v2\runtime\state.json
```
Look for:
- `open_positions[*].mark_source` — current value for all 3 positions
- `open_positions[*].current_price` and `open_positions[*].mark` — to assess whether marks look live or stale
- `last_guard_result`, `guard`, `last_guard_reason`, `last_guard_reasons`, `guard_reasons` — any guard payload currently present
- `mode.switch_reason`, `pnl.session_pnl` — any loss/drawdown condition
- Any field with "max_down", "drawdown", "session_loss", "max_loss" in its name or value

### Step 2 — Read dashboard_server.py — mark_source decision logic
Find the exact function and lines in `dashboard_server.py` that:
- Read marks from the state hub or stream
- Decide whether `mark_source` is `stream`, `rest_fallback`, or `poll_fallback`
- What condition triggers the switch to `rest_fallback` (staleness threshold? explicit flag? stream disconnect?)
- Whether there is a per-position decision or a global fallback mode

### Step 3 — Read dashboard_server.py — guard payload assembly
Find the exact code in `dashboard_server.py` that:
- Assembles the `last_guard_result`, `guard`, or equivalent field in the `/api/state` or `/api/stream/state` payload
- Whether any "max down" or similar text is generated server-side before reaching the client
- Whether this field is read from `runtime/state.json` directly, computed from runtime state, or built from another source

### Step 4 — Check dashboard logs for fallback frequency
In `logs/dashboard.log` or `logs/dashboard_err.log`:
- Count or estimate how frequently `[STALE_POLL]` lines appear in the last N minutes
- Are `[STALE_POLL]` lines appearing on every loop or just occasionally?
- Any stream reconnect/disconnect events that would explain sustained REST fallback

### Step 5 — One additional file only if needed
If Steps 1–4 do not explain:
- Why `rest_fallback` is sustained (e.g., stream confirmed down/degraded): read the relevant section of `core/polymarket_stream.py` that tracks stream health or fallback trigger
- Where the guard payload write comes from: read only the specific section of `bot_core.py` that writes `last_guard_result` or `guard_reasons` to `runtime/state.json`

**Justify any extra file explicitly in your result.**

---

## Questions you must answer

**Q1 — mark_source production chain:**
What exact function and condition in `dashboard_server.py` sets `mark_source` to `stream` vs `rest_fallback` vs `poll_fallback` per position?

**Q2 — Fallback trigger condition:**
What specific staleness threshold, flag, or stream-health check causes the switch to `rest_fallback`? (e.g., mark age > N seconds? stream not connected? explicit field on state hub mark object?)

**Q3 — Current fallback severity:**
For the current live session, is `rest_fallback` appearing:
- (a) rarely and normally — isolated to 1 position, brief window
- (b) intermittently but acceptably — appears across positions but stream recovers
- (c) too often / degraded — most marks are from REST fallback, stream is not delivering
- (d) effectively the main source — all positions on REST fallback, stream not contributing
- (e) unclear from available evidence

**Q4 — Guard/warning payload chain:**
What exact code path writes the `last_guard_result` / `guard` / `guard_reasons` field to the payload that dashboard.html renders? Is it:
- Written by bot_core to `state.json` and served from there by dashboard_server.py?
- Assembled server-side by dashboard_server.py from runtime state?
- Something else?

**Q5 — "max down" wording origin:**
Can you confirm or rule out that any "max down" style text is currently present in:
- `runtime/state.json` (any field)
- The `/api/state` or `/api/stream/state` payload
- Any log line in `logs/dashboard.log` or `logs/bot_baseball_20260410.log` (grep only — do not read the full log)

**Q6 — Root cause conclusion:**
For each symptom, classify:
- feed/stream problem (stream not delivering for these markets)
- mark-source payload problem (fallback logic triggering incorrectly)
- stale/cached state problem (old state written before restart not cleared)
- guard-message payload problem (wrong text being written upstream)
- cosmetic/expected behavior
- mixed issue

---

## Required output

Write result to:
```
C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001.json
```

Structure:
```json
{
  "task_id": "MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001",
  "status": "DONE",
  "read_only_confirmed": true,

  "current_runtime_snapshot": {
    "open_positions_mark_sources": [],
    "guard_fields_present": {},
    "any_max_down_or_drawdown_field": false,
    "notes": ""
  },

  "1_mark_source_production_chain": {
    "function_name": "",
    "file": "dashboard_server.py",
    "decision_logic": "",
    "stream_condition": "",
    "rest_fallback_condition": "",
    "poll_fallback_condition": ""
  },

  "2_fallback_trigger": {
    "trigger_condition": "",
    "staleness_threshold": "",
    "stream_health_check": "",
    "evidence": ""
  },

  "3_fallback_severity": {
    "severity_label": "(a/b/c/d/e)",
    "evidence": "",
    "stale_poll_frequency_estimate": "",
    "stream_health_assessment": ""
  },

  "4_guard_payload_chain": {
    "write_origin": "",
    "field_name_in_payload": "",
    "how_dashboard_reads_it": "",
    "evidence": ""
  },

  "5_max_down_wording_origin": {
    "found_in_state_json": false,
    "found_in_api_payload": false,
    "found_in_logs": false,
    "conclusion": ""
  },

  "6_root_cause_classification": {
    "mark_rest_issue": "",
    "warning_message_issue": ""
  },

  "severity_assessment": {
    "mark_rest": "",
    "warning_message": "",
    "combined": ""
  },

  "recommended_next_action": {
    "action": "no_action | dashboard_fix | server_fix | stream_fix | combined_fix",
    "order_if_two_step": "",
    "rationale": ""
  },

  "files_read": [],
  "files_modified": [],
  "extra_files_justified": []
}
```

---

## Acceptance criteria

- [ ] `read_only_confirmed: true`
- [ ] Exact function + condition in `dashboard_server.py` that sets `mark_source`
- [ ] Explicit staleness/stream-health trigger condition for `rest_fallback`
- [ ] Severity label (a/b/c/d/e) for current fallback frequency with evidence
- [ ] Guard/warning payload write chain traced to source
- [ ] Explicit answer on whether "max down" text is present anywhere in current runtime state
- [ ] Root-cause classification for both symptoms
- [ ] Result written to correct path

---

## Prior task context

Prior task DASHBOARD_MARK_SOURCE_AND_GUARD_MESSAGE_AUDIT_001 confirmed:
- `dashboard.html` does not hardcode "max down" — renders raw `state.last_guard_result` / `state.guard`
- `dashboard_server.py` does produce `rest_fallback` via `[STALE_POLL]` log lines
- Live SSE showed `mlb-wsh-mil` with `mark_source='rest_fallback'`
- `state.json` guard fields were null at last audit

Use this context to avoid re-tracing what is already known. Go deeper.
