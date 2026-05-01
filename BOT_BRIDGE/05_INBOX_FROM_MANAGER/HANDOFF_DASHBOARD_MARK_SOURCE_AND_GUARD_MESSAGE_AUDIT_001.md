# HANDOFF — DASHBOARD_MARK_SOURCE_AND_GUARD_MESSAGE_AUDIT_001
**Priority:** MEDIUM
**Type:** Read-only audit
**Issued:** 2026-04-10
**Scope:** NARROW — two dashboard display issues only. Do not sweep the repo.

---

## One-sentence task

Determine why position cards are showing `mark REST` (fallback pricing) instead of live stream marks, and why the dashboard is displaying a "max down" / max-loss style warning message when the actual runtime guard reasons are `micro_depth_too_low` and `micro_spread_too_wide`.

---

## Context for the worker

The operator has observed two symptoms on the live dashboard after the current session restart:

**Symptom 1 — `mark REST` chip on position cards:**
Cards are showing a yellow warning chip indicating `mark REST` (REST fallback pricing). The live Polymarket price stream should be providing mark data. This fallback indicates either the stream is not delivering price updates for those assets, or the REST fallback is triggering incorrectly.

**Symptom 2 — "max down" style warning message in dashboard:**
The dashboard is displaying a message that resembles a max-loss / max-drawdown warning ("max down" or similar text), but the current runtime guard block reasons, as visible in recent state/logs, are `micro_depth_too_low` and `micro_spread_too_wide`. There is no active session loss cap or drawdown condition that should produce a max-down message.

**Known system state at time of audit:**
- Fresh restart completed recently (2026-04-10, post BRIDGE_ENTRY_GATE_WIRING_FIX_001 patch)
- 3 open positions (trades 223, 237, 238)
- Bot at MAX_CONCURRENT_TRADES capacity (3/3)
- BRIDGE SKIP — at capacity logged on each loop

---

## What you must NOT do

- Edit any code
- Edit `.env`
- Restart any process
- Write to any DB
- Do a broad repo sweep
- Read every file in the repo
- Read bot_core.py, core/risk.py, launch_all.py, .env, or trades_sports.db (unless absolutely required for a specific chain trace — justify explicitly)

---

## Where to look, in order

### Step 1 — Read current runtime state (START HERE)
```
C:\Users\johnny\Desktop\sports_bot_v2\runtime\state.json
```
This is the ground truth for everything the dashboard displays. Read it fully.
Look for:
- `guard_reasons` — what guard blocks are active right now
- `open_positions[*].mark_source` — what mark source is set per position
- `mode.switch_reason` — any drawdown or loss-related mode switch reason
- `status_line` — what the bot is reporting as its current status
- `pnl.session_pnl` — any session P&L loss condition
- any `max_down`, `drawdown`, `session_loss` fields

### Step 2 — Check dashboard logs for mark_source and warning messages
Search recent entries in `logs/dashboard.log` or `logs/dashboard_err.log`:
- Any errors serving `/api/state`
- Any mark-source related logging
- Any REST fallback trigger logging

### Step 3 — Read dashboard.html for rendering logic
Find the two display chains in `dashboard.html`:
- **mark_source chip:** search for `mark REST`, `mark_source`, `rest_fallback`, `poll_fallback` — find the JS that renders the chip and what payload field drives it
- **warning message / "max down" text:** search for `max down`, `max_down`, `drawdown`, `session_loss`, `guard_reasons`, the status bar / alert banner rendering logic — find exactly what payload field and condition triggers the message

### Step 4 — Read dashboard_server.py for payload mapping
Find how `mark_source` and guard/warning fields are built into `/api/state`:
- Where `mark_source` is set per position (is it per-OB snapshot? per stream vs REST flag?)
- Whether the guard_reasons or mode state are transformed before being sent to the client
- Whether any "max down" or drawdown message is injected server-side

### Step 5 — One code file only if needed
If Steps 1–4 don't explain why REST fallback is active (e.g., state.json says `mark_source=rest_fallback` but you can't find the trigger), read `dashboard_server.py`'s mark-source decision logic or the relevant section of `core/polymarket_stream.py` only to understand when REST fallback is triggered.
**Justify use of any extra file explicitly in your result.**

---

## Questions you must answer

**Q1 — mark_source chain:**
What exact field/value in `state.json` → `/api/state` → `dashboard.html` causes the `mark REST` chip to appear?

**Q2 — mark REST cause:**
Is the current `mark REST` behavior caused by:
- (a) Normal short-term stale-mark fallback (stream OK, just briefly stale)
- (b) Broken or disconnected live market stream
- (c) Missing stream updates for specific assets (those 3 open markets not in stream subscription)
- (d) Payload mapping error (field set to wrong value despite stream being healthy)
- (e) Another concrete cause

**Q3 — "max down" message chain:**
What exact condition/field in the runtime state or dashboard rendering causes the "max down" style warning message to appear?

**Q4 — actual guard reasons:**
What are the exact current `guard_reasons` values in the live runtime state?

**Q5 — message accuracy:**
Does the displayed message match current runtime truth, or is the dashboard rendering an incorrect/stale/misleading label for a real condition?

**Q6 — root cause classification:**
For each symptom, classify:
- feed/stream problem
- dashboard HTML rendering/binding problem
- dashboard_server.py payload mapping problem
- real underlying runtime condition being correctly displayed
- mixed issue

---

## Required output

Write result to:
```
C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_DASHBOARD_MARK_SOURCE_AND_GUARD_MESSAGE_AUDIT_001.json
```

Structure:
```json
{
  "task_id": "DASHBOARD_MARK_SOURCE_AND_GUARD_MESSAGE_AUDIT_001",
  "status": "DONE",
  "read_only_confirmed": true,

  "current_runtime_state_summary": {
    "guard_reasons": [],
    "open_positions_mark_sources": [],
    "mode": {},
    "status_line": "",
    "any_loss_or_drawdown_condition": false
  },

  "1_mark_source_chain": {
    "field_in_state_json": "",
    "value_observed": "",
    "how_dashboard_renders_it": "",
    "payload_path": "state.json → /api/state → dashboard.html JS → chip display"
  },

  "2_mark_rest_cause": {
    "cause_label": "(a/b/c/d/e)",
    "cause_description": "",
    "evidence": "",
    "is_expected_behavior": true,
    "severity": "cosmetic | operator-confusion | pricing-risk"
  },

  "3_warning_message_chain": {
    "message_text_displayed": "",
    "field_or_condition_that_triggers_it": "",
    "actual_runtime_value": "",
    "is_message_accurate": true
  },

  "4_actual_guard_reasons": [],

  "5_message_accuracy": {
    "displayed_message_matches_runtime": true,
    "discrepancy_description": ""
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
- [ ] `mark_source` chain documented from state.json to chip display
- [ ] Explicit cause label (a/b/c/d/e) for `mark REST` with evidence
- [ ] Explicit identification of what triggers the "max down" style message
- [ ] Actual guard_reasons values from live runtime state
- [ ] Assessment of whether displayed message is accurate or misleading
- [ ] Root-cause classification for both symptoms
- [ ] Result written to correct path

---

## Read `TASK_DASHBOARD_MARK_SOURCE_AND_GUARD_MESSAGE_AUDIT_001.json` for machine-readable record.
