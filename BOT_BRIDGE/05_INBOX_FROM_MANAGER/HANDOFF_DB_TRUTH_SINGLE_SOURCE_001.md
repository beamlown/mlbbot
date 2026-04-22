<!-- writer: manager, task_id: DB_TRUTH_SINGLE_SOURCE_001, patch_id: pending, written_at: 2026-04-18T17:35:49Z, attempt: 1 -->

# HANDOFF: DB_TRUTH_SINGLE_SOURCE_001

## Status
QUEUED — P1 phase, observability. Independent. Closes the loop on prior
DASHBOARD_TRUTH work by extending to any remaining dashboard panels.

## What you are doing
Audit every panel and endpoint on the dashboard to verify it reads from
`trades_sports.db` as the single source of truth — no in-memory computation,
no parallel state, no paper_trades.db. Fix any panel that violates this.

## Why this exists
The operator is using the dashboard to judge whether the model has edge. If
any panel shows a number that wasn't persisted to DB, we can't trust it.
Prior DASHBOARD_TRUTH work fixed specific issues; this task is a comprehensive
sweep + closure. Also a prerequisite for the upcoming ATTRIBUTION_DASHBOARD
panels to be trustworthy.

## Target files (read-mostly; write only where you find a violation)
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html`
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_v2.html` (confirm which is authoritative)
- Any helper module imported by the dashboard

## Audit process

### 1. Inventory
For every `/api/*` endpoint, list:
- endpoint path
- handler function (file:line)
- data source (SELECT from trades_sports.db / computed / cached / cross-file)
- whether it reads paper_trades.db (the old separate DB, should be dead)
- whether it reads any in-memory dict that isn't reconstructed from DB on
  process restart

### 2. Violation classes
- **V1:** reads paper_trades.db (old DB, should be retired for observability)
- **V2:** reads in-memory cache that is not DB-backed (cache may be stale)
- **V3:** computes metric from logs/JSONL file without cross-checking DB
- **V4:** has a fallback path that silently substitutes a different source
  (violates "if field is NULL, show n/a — don't guess")

### 3. Fix
For every violation found, rewrite the handler to read from trades_sports.db
only. If the needed data isn't in DB, return an explicit "n/a" field rather
than computing a proxy.

### 4. Retire paper_trades.db usage (if found)
If any endpoint still reads paper_trades.db: switch it, and record the
retirement in the result JSON. Do NOT delete paper_trades.db — only stop
reading from it. (Deletion is a separate operator decision.)

## Scope guardrail
- This task is ABOUT existing panels. You may NOT add new panels.
- If a panel reads from a source that's actually correct for its purpose
  (e.g., `runtime/state.json` for live bot state is fine — that's operational
  state, not trade history), document the exception with reasoning.

## Output / deliverables
1. Full inventory table (every endpoint + data source classification)
2. Diff for each violation fixed
3. Result JSON at `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_DB_TRUTH_SINGLE_SOURCE_001.json`

## Result JSON fields required
```json
{
  "task_id": "DB_TRUTH_SINGLE_SOURCE_001",
  "status": "ok",
  "endpoints_audited": 0,
  "violations_found": [
    {"endpoint": "...", "class": "V2", "was": "...", "now": "..."}
  ],
  "clean_endpoints": ["..."],
  "documented_exceptions": [
    {"endpoint": "/api/bot_state", "source": "runtime/state.json", "why": "operational state, not historical"}
  ],
  "paper_trades_db_still_read": false,
  "files_changed": ["..."]
}
```

## Do NOT do
- Do not add new dashboard panels (that is ATTRIBUTION_DASHBOARD_001)
- Do not change attribution schema
- Do not delete paper_trades.db
- Do not modify bot_core.py or trading code
- Do not change mark-source authority
- No real-money paths
