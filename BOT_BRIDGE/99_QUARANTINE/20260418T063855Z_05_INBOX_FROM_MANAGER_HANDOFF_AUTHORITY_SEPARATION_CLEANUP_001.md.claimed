# HANDOFF_AUTHORITY_SEPARATION_CLEANUP_001

## Status: ACTIVE

**Title**: Remove local MLB origination code from sports_bot_v2 and decouple execution gating from mlb_model
**Priority**: HIGH
**Subsystem**: authority-model
**Issued**: 2026-04-17
**Assigned**: SONNET_MANAGER

---

## What this task is

_(edit me — auto-generated stub)_

## Allowed files
- `C:\Users\johnny\Desktop\sports_bot_v2\bot_core.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\core\signal_base.py`
- `C:\Users\johnny\Desktop\mlb_model\integration\recommendation_api.py`
- `C:\Users\johnny\Desktop\mlb_model\core\execution_guard.py`

## Acceptance

- bot_core.py no longer contains ALLOW_LOCAL_MLB_ORIGINATION or local signal generation for MLB
- bot_core.py bridge path (560-637) compiles and is logically unchanged
- signal_base.py MLB decision engine removed or MLB branch isolated
- recommendation_api.py no longer imports or calls execution_guard functions
- recommendation_api.py no longer contains ROLLBACK_DISABLE
- execution_guard.py deleted or emptied with no remaining importers
- No other allowed file has unresolved references to removed symbols
- Result written to 06_OUTBOX_FROM_WORKER as RESULT_AUTHORITY_SEPARATION_CLEANUP_001.json

---

_Auto-generated stub. Replace with narrative brief; the dashboard will not overwrite this file once it exists._

---
## RETRY CONTEXT (auto-generated — attempt 4)

A previous run failed on this task. Before you start, read this:

- prior status: `fail`
- prior summary: (no RESULT_JSON emitted and no RESULT file written)
- prior run id: `RUN_09882819C3C7`

### What went wrong
The previous worker did not produce a RESULT for **AUTHORITY_SEPARATION_CLEANUP_001**. Common causes: (a) the worker drifted to a different task, (b) the worker never wrote `RESULT_AUTHORITY_SEPARATION_CLEANUP_001.json`, (c) the worker exited before completing the scope.

### What to do differently this attempt
1. Work ONLY on `AUTHORITY_SEPARATION_CLEANUP_001`. Ignore every other task name you see.
2. Write your result to `BOT_BRIDGE/06_OUTBOX_FROM_WORKER/RESULT_AUTHORITY_SEPARATION_CLEANUP_001.json` and NO other file.
3. If the scope is unclear, emit `status: blocked` with a specific question.
   Do NOT substitute a different task you think you know.

### Prior stdout tail (for diagnosis)
```
[session] id=44dfd77b model=claude-haiku-4-5-20251001
[rate-limit] status=rejected
[thinking] The user is telling me that I'm a WORKER and I need to read the HANDOFF and produce the requested change. Let me first understand what task I'm supposed to be working on.
I'm ready to work on a task. Let me check the inbox to see which task you'd like me to handle.
[tool→ Bash] command=ls -la "BOT_BRIDGE/05_INBOX_FROM_MANAGER/" | head -30
[tool← 2461B] total 1642
[thinking] I see there are many handoff files. Since the user said "Read the HANDOFF" (singular) but didn't specify which one, I should ask them which task they want me to work on. However, let me check if ther…
I see there are many tasks in the inbox. Which task would you like me to work on? Could you provide the task name or number (e.g., `TASK_AUTHORITY_SEPARATION_CLEANUP_001`)?

Alternatively, I can check if there's a specific task that's currently in progress or was most recently queued. Let me know which handoff you'd like me to read.
[done] ok duration=11730ms turns=2
```
