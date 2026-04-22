<!-- writer: manager, task_id: SHADOW_ENGINE_RENAME_001, patch_id: pending, written_at: 2026-04-18T17:35:49Z, attempt: 1 -->

# HANDOFF: SHADOW_ENGINE_RENAME_001

## Status
QUEUED — P1 phase, observability cleanup. Independent.

## What you are doing
Rename `shadow_engine` to `mlb_recommendation_api` across the launcher, log
file, internal references, and dashboard UI strings. The legacy name misleads
the operator — the process is actually the MLB model's recommendation API,
not a shadow trader.

## Why this exists
`launch_all.py:22-26` shows the process named `shadow_engine` actually runs
`mlb_model/integration/recommendation_api`. Operator reported confusion: "I
don't know what shadow_engine does anymore." Clearing this once kills
permanent confusion.

## Target files (probable — grep to confirm)
- `C:\Users\johnny\Desktop\sports_bot_v2\launch_all.py` — process spec entry
- `C:\Users\johnny\Desktop\sports_bot_v2\logs\shadow_engine.log` — leave the
  existing log file, but new writes go to `mlb_recommendation_api.log`
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py` — any process
  health UI referencing `shadow_engine`
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html` / `dashboard_v2.html` —
  UI strings
- `C:\Users\johnny\Desktop\sports_bot_v2\runtime\*` — process state files if any
- `C:\Users\johnny\Desktop\sports_bot_v2\restart_bot.bat` / `run_control_plane.bat`
  if referenced

## Rename scope
Replace `shadow_engine` with `mlb_recommendation_api` ONLY for this process
identifier. Do NOT blind-replace in unrelated contexts — there may be
historical handoff docs or RESULT files that reference the old name and those
should be left alone.

Use case-preserving replacement:
- `shadow_engine` → `mlb_recommendation_api`
- `Shadow_engine` → `Mlb_recommendation_api`
- `SHADOW_ENGINE` → `MLB_RECOMMENDATION_API`

## Log file handling
- Keep `logs/shadow_engine.log` as-is (historical record)
- New writes go to `logs/mlb_recommendation_api.log`
- Add a header line on startup noting the rename so anyone tailing the new
  file understands

## Dashboard
Wherever the dashboard shows process health, use the new name. Tooltip/hover
should say: "MLB model recommendation API — discovers live Polymarket events,
parses slugs, matches vs MLB registry, emits recommendations."

## Scope guardrails — do NOT touch
- `BOT_BRIDGE/` directory — old handoff names reference `shadow_engine`
- The actual `integration/recommendation_api` source code — no functional changes
- Any historical log files (read-only)
- DB rows or trade forensics JSONL
- Any real-money code path

## Output / deliverables
1. Modified files with rename applied
2. List of files changed + line counts
3. Result JSON at `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_SHADOW_ENGINE_RENAME_001.json`

## Result JSON fields required
```json
{
  "task_id": "SHADOW_ENGINE_RENAME_001",
  "status": "ok",
  "files_changed": ["..."],
  "replacement_count": 0,
  "log_file_new": "logs/mlb_recommendation_api.log",
  "dashboard_label_updated": true,
  "bot_bridge_left_untouched_confirmation": "no files under BOT_BRIDGE/ were modified"
}
```

## Do NOT do
- Do not modify recommendation_api itself
- Do not modify BOT_BRIDGE contents
- Do not change any functional behavior of the process
- Do not rename the log directory
- No real-money paths
