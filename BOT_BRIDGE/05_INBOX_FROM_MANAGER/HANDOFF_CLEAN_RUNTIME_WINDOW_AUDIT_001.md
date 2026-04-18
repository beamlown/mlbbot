# HANDOFF: CLEAN_RUNTIME_WINDOW_AUDIT_001
## Status: DEFERRED — Do NOT execute this task

---

## ⛔ THIS TASK IS DEFERRED. DO NOT RUN IT.

**Activation condition:** Bot must have ≥30 trades opened after `2026-04-11T10:57:33 UTC` (exact ISO timestamp, not date string).

**Current status (as of 2026-04-17):** 0 trades in the clean era. Bot last traded 2026-04-11T05:00 UTC (zombie-process era, pre-restart). No new trades have opened since the verified clean restart at 10:57:33 UTC.

**Prior result:** `BOT_BRIDGE/06_OUTBOX_FROM_WORKER/RESULT_CLEAN_RUNTIME_WINDOW_AUDIT_001.json` — confirms n=0 clean era trades.

---

## When activated (n≥30 reached):

**Task:** Evaluate E1+E2 proof in the verified clean era only.

**Query anchor:**
```sql
SELECT * FROM trades WHERE ts_open > '2026-04-11T10:57:33'
```
Do NOT use `ts_open > '2026-04-11'` — that includes zombie-process trades from 00:00–05:00 UTC.

**Criteria to evaluate:**
- E1: avg_pnl_net > 0
- E2: actual_WR > break_even_WR
- E6: confidence monotonically predictive (bucket breakdown)
- E7: E1+E2 for conf≥0.65 + entry≥0.22 universe

**Database:** `C:\Users\johnny\Desktop\sports_bot_v2\trades_sports.db` (read-only)

**Output:** Write result to `BOT_BRIDGE/06_OUTBOX_FROM_WORKER/RESULT_CLEAN_RUNTIME_WINDOW_AUDIT_001.json`

---

*Manager note (2026-04-17): Prior worker output from this file was causing dispatch contamination — 6 workers across unrelated tasks executed this audit instead of their assigned tasks because this file was served as shared context containing a completed, detailed audit report. File cleared and replaced with this deferred brief.*

---
## RETRY CONTEXT (auto-generated — attempt 4)

A previous run failed on this task. Before you start, read this:

- prior status: `fail`
- prior summary: (no RESULT_JSON emitted and no RESULT file written)
- prior run id: `RUN_954A996E6DDE`

### What went wrong
The previous worker did not produce a RESULT for **CLEAN_RUNTIME_WINDOW_AUDIT_001**. Common causes: (a) the worker drifted to a different task, (b) the worker never wrote `RESULT_CLEAN_RUNTIME_WINDOW_AUDIT_001.json`, (c) the worker exited before completing the scope.

### What to do differently this attempt
1. Work ONLY on `CLEAN_RUNTIME_WINDOW_AUDIT_001`. Ignore every other task name you see.
2. Write your result to `BOT_BRIDGE/06_OUTBOX_FROM_WORKER/RESULT_CLEAN_RUNTIME_WINDOW_AUDIT_001.json` and NO other file.
3. If the scope is unclear, emit `status: blocked` with a specific question.
   Do NOT substitute a different task you think you know.

### Prior stdout tail (for diagnosis)
```
- **I1 (available_cash)**: Missing `fees_usd` in committed calculation â†’ Added to SQL query and summation
- **I2 (live_equity bid)**: Using `current_price` (could be ask) instead of `best_bid` â†’ Fixed to use held-side bid

**Invariants Confirmed:**
- **I3, I4, I5**: Session PnL anchoring, lifetime realized PnL accumulation, and no double-counting all working correctly

**Deliverables:**
1. Fixed `sports_bot_v2/dashboard_server.py` (lines 310-319 for I1, 476-480 for I2)
2. Created `BANKROLL_ACCOUNTING_SPEC_001.md` with canonical formulas
3. Wrote `RESULT_BANKROLL_SESSION_RULES_001.json` with verdicts and details

All code compiles successfully âœ“
```
