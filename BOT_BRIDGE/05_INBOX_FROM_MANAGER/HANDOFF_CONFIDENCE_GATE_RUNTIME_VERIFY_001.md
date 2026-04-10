# HANDOFF — CONFIDENCE_GATE_RUNTIME_VERIFY_001
**Priority:** HIGH
**Type:** Read-only runtime verification
**Issued:** 2026-04-10
**Scope:** NARROW — do not sweep the repo. Answer 6 specific questions only.

---

## One-sentence task

Determine whether the live `sports_bot_v2` runtime is actually enforcing the new `MIN_ENTRY_CONFIDENCE=0.60` gate against bridge-issued entries, or whether trades 223 and 224 (confidence 0.3353 and 0.3996) entered via a path that bypasses the gate or opened before the relevant restart.

---

## Background (manager pre-work)

The following facts are already established from BOT_BRIDGE artifacts. Do not re-derive these — use them as starting data:

### Restart time (from RESULT_PROCESS_CLEANUP_VERIFY_001.json)
- `bot_core.py` PID 24800 was created at `20260410144043.254391-300` (CDT, UTC-5)
- **Restart timestamp: 2026-04-10T14:40:43-05:00 = 2026-04-10T19:40:43Z**

### Suspicious trades (from user-supplied confidence audit)
| trade_id | confidence | ts_open (UTC) | delta from restart |
|----------|-----------|---------------|--------------------|
| 223      | 0.3353     | 2026-04-10T22:44:07Z | +3h 3m POST-restart |
| 224      | 0.3996     | 2026-04-10T22:47:37Z | +3h 7m POST-restart |

Both trades opened **well after** the confirmed restart. Both have confidence well below 0.60. This is the suspected violation.

### MIN_ENTRY_CONFIDENCE_001 implementation (from RESULT_MIN_ENTRY_CONFIDENCE_001.json)
- Gate added to: `sports_bot_v2/core/risk.py`
- Gate position: FIRST gate in `check_entry_gates()` waterfall — before OB/DB/spread work
- Returns `False` with reason `confidence_too_low:X:0.600`
- Handles `None` confidence (treated as below floor)
- Env var: `MIN_ENTRY_CONFIDENCE=0.60` added to `.env`
- `restart_required: true` was noted in the result

---

## The 6 questions you must answer

1. **What was the exact restart time after the 4 approved risk/sizing tasks?**
   - Manager has established: **2026-04-10T19:40:43Z** (bot_core.py PID 24800 creation)
   - Confirm or correct using log evidence if bot logs show a startup line
   - If a second restart occurred after that, report it

2. **Did trades 223 and 224 open before or after that restart?**
   - Manager has established: AFTER (by 3h+)
   - Confirm exact trade timestamps from `trades_sports.db` with: `SELECT id, confidence, ts_open FROM trades WHERE id IN (223, 224)`
   - State the before/after verdict explicitly

3. **Does the live entry path for bridge-issued trades pass through `check_entry_gates()`?**
   - Read `sports_bot_v2/bot_core.py` — find the bridge entry code path
   - Confirm whether `check_entry_gates()` is called before `open_trade()` / `paper_exec`
   - Cite file and approximate line number
   - This is the most critical structural question

4. **Is `MIN_ENTRY_CONFIDENCE=0.60` loaded in the live runtime path?**
   - Read `sports_bot_v2/core/risk.py` — confirm `MIN_ENTRY_CONFIDENCE` env var is present and read at module load
   - Check `.env` to confirm `MIN_ENTRY_CONFIDENCE=0.60` is present
   - Note: do NOT edit either file

5. **Are there log lines showing `confidence_too_low` rejections after restart (19:40:43Z)?**
   - Search recent bot logs for `confidence_too_low` or `MIN_ENTRY_CONFIDENCE`
   - If found: report timestamps and confidence values of rejected signals
   - If NOT found: this is significant — note whether it means no signals failed, or whether the log call is missing

6. **If low-confidence trades opened after restart, what is the most likely root cause?**
   Evaluate these hypotheses in order:
   - (a) **Bridge path bypasses `check_entry_gates()`** — bridge-issued entries use a fast path that skips the gate
   - (b) **Confidence stored in DB differs from confidence at gate time** — gate may have used a different/stale value
   - (c) **Stale process** — a second `bot_core.py` was running from before the restart and never killed
   - (d) **Restart mismatch** — the restart confirmed by PROCESS_CLEANUP_VERIFY_001 was for a different change, not MIN_ENTRY_CONFIDENCE_001
   - (e) **Gate disabled** — `MIN_ENTRY_CONFIDENCE=0.0` in .env, or env var not read
   - (f) **Other concrete cause**

---

## Allowed files / sources (hard limit — read no others)

| Source | What to do |
|--------|-----------|
| `RESULT_PROCESS_CLEANUP_VERIFY_001.json` (BOT_BRIDGE) | Already read by manager — use data above |
| `trades_sports.db` | SELECT only: `SELECT id, confidence, ts_open FROM trades WHERE id IN (223, 224)` |
| Recent bot logs | Search for startup lines, `confidence_too_low`, any entry/gate log lines after 19:40Z |
| `sports_bot_v2/bot_core.py` | Read to confirm bridge entry path calls `check_entry_gates()` |
| `sports_bot_v2/core/risk.py` | Read to confirm `MIN_ENTRY_CONFIDENCE` is loaded and used |
| `sports_bot_v2/.env` | Read to confirm `MIN_ENTRY_CONFIDENCE=0.60` is present |
| `sports_bot_v2/core/model_bridge.py` | Read ONLY if bot_core.py read raises a question about handoff path — justify explicitly if used |

---

## Hard limits — DO NOT

- Do NOT edit any code
- Do NOT edit `.env`
- Do NOT write to `trades_sports.db`
- Do NOT restart any process
- Do NOT read dashboard files, runtime state files (other than DB SELECT), or any file not listed above
- Do NOT do a broad repo sweep
- Do NOT write to any BOT_BRIDGE file other than the result file

---

## Required deliverables

Write your result to:
```
C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_CONFIDENCE_GATE_RUNTIME_VERIFY_001.json
```

Structure:
```json
{
  "task_id": "CONFIDENCE_GATE_RUNTIME_VERIFY_001",
  "status": "DONE",
  "read_only_confirmed": true,

  "1_restart_timeline": {
    "confirmed_restart_ts_utc": "<ISO8601 or 'confirmed: 2026-04-10T19:40:43Z'>",
    "evidence_source": "<log line or artifact>",
    "additional_restarts": "<none | describe>",
    "verdict": "<confirmed | corrected — new time is X>"
  },

  "2_trade_timeline": {
    "trade_223": {
      "id": 223,
      "confidence": "<from DB>",
      "ts_open_utc": "<from DB>",
      "before_or_after_restart": "<BEFORE | AFTER>"
    },
    "trade_224": {
      "id": 224,
      "confidence": "<from DB>",
      "ts_open_utc": "<from DB>",
      "before_or_after_restart": "<BEFORE | AFTER>"
    },
    "verdict": "<both BEFORE | both AFTER | mixed>"
  },

  "3_gate_path_verification": {
    "bridge_entry_calls_check_entry_gates": "<YES | NO | UNCLEAR>",
    "file": "bot_core.py",
    "approx_line": "<line number or range>",
    "notes": "<any relevant detail>"
  },

  "4_runtime_config": {
    "min_entry_confidence_in_env": "<YES=0.60 | NO | value found>",
    "min_entry_confidence_in_risk_py": "<YES | NO>",
    "gate_would_be_active": "<YES | NO | conditional>"
  },

  "5_log_evidence": {
    "confidence_too_low_rejections_found": "<YES | NO>",
    "rejection_count_post_restart": "<N or 0>",
    "sample_rejections": [],
    "low_confidence_accepts_found": "<YES | NO>",
    "sample_accepts": [],
    "notes": "<what was or wasn't in logs>"
  },

  "6_root_cause": {
    "hypothesis_tested": ["(a) bypass", "(b) value mismatch", "(c) stale process", "(d) restart mismatch", "(e) gate disabled"],
    "most_likely_cause": "<label and description>",
    "confidence_in_finding": "<HIGH | MEDIUM | LOW>",
    "is_real_bug": "<YES | NO | UNCERTAIN>"
  },

  "next_action": {
    "recommendation": "<no_action | queue_fix | queue_restart | queue_narrower_audit>",
    "rationale": "<one sentence>"
  },

  "files_read": [],
  "files_modified": []
}
```

---

## Acceptance criteria

- [ ] `read_only_confirmed: true`
- [ ] No code modified, no DB writes, no restarts
- [ ] Restart time confirmed or corrected with evidence
- [ ] Explicit BEFORE/AFTER verdict for trades 223 and 224
- [ ] Explicit YES/NO on whether bridge entries use `check_entry_gates()`
- [ ] Explicit YES/NO on whether 0.60 floor is loaded in live env/code
- [ ] Explicit conclusion on whether a real bug exists
- [ ] `next_action` field populated
- [ ] Result written to `RESULT_CONFIDENCE_GATE_RUNTIME_VERIFY_001.json`

---

## Read `TASK_CONFIDENCE_GATE_RUNTIME_VERIFY_001.json` for machine-readable task record.
