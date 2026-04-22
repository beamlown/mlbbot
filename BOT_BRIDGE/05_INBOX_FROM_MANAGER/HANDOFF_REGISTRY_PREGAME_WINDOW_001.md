<!-- writer: manager, task_id: REGISTRY_PREGAME_WINDOW_001, patch_id: pending, written_at: 2026-04-18T17:35:49Z, attempt: 1 -->

# HANDOFF: REGISTRY_PREGAME_WINDOW_001

## Status
QUEUED — P1 phase, observability / discovery clarity. Independent.

## What you are doing
Fix a log-noise + discovery-correctness issue: the MLB registry (used by the
recommendation API / discovery loop) currently holds only TODAY's games.
Polymarket exposes events for future dates (e.g., `mlb-bal-kc-2026-04-20`),
which then log as `no_registry_match` on 2026-04-18 — generating noise and
potentially masking real matching bugs.

## Why this exists
Observed in `logs/shadow_engine.log` on 2026-04-18:
- 40 events parsed correctly but were rejected with `no_registry_match` or
  `not_live` because they are for 2026-04-20
- Registry was populated with today only (2026-04-18): `KCR@NYY`, `CIN@MIN`,
  `NYM@CHC`, ...
- Each of those 40 logs a verbose registry dump, polluting the log

This is a design question more than a bug: either
- **(a) Expand the registry window** to N days so future-scheduled events get
  a real registry match, OR
- **(b) Classify future-day events as `FUTURE_SCHEDULED`** at the parse stage
  and skip the registry check entirely, with a single summary log line

Pick (b) unless you have a compelling reason for (a) — (b) is lower-risk and
fixes the log noise without changing registry semantics. Explain your choice
in the result JSON.

## Target files
- `C:\Users\johnny\Desktop\mlb_model\integration\recommendation_api.py` — the
  discovery + registry-check loop (confirm path; this is what runs as the
  launcher's `shadow_engine` process)
- Any related registry module imported by it

## Required behavior — option (b) recommended

### At parse stage
Every event has a parsed `event_date`. Compare to `today`:
- If `event_date == today` → proceed with existing registry check (unchanged)
- If `event_date > today` → classify as `FUTURE_SCHEDULED`, skip registry check
  entirely, do NOT log the full registry dump
- If `event_date < today` → classify as `PAST` (shouldn't happen often;
  existing handling fine)

### Log change
Current per-event verbose dump → replace with a single end-of-loop summary:
```
Discovery: 0 live | skipped: 86 non-mlb/date, 0 closed, 67 non-moneyline/no-keyword, 0 unparseable, 40 not-live, X future_scheduled, 0 duplicate_event_market
```
And a single `INFO future events: [mlb-bal-kc-2026-04-20, mlb-stl-mia-2026-04-20, ...]` line if count > 0.

## Option (a) — registry window expansion
Only choose this if the bot actually trades pre-game markets. If pre-game
trading is in scope, the registry should know about them. Scope then expands:
- Registry loader fetches schedule for `today .. today + N` (configurable, default 2)
- Pre-game markets get matched and can enter discovery
- But: bot must still have a separate "is this live right now?" check before
  it places any trade

Verify current bot behavior first: does it trade pre-game or live-only? Read
`bot_core.py` + `core/risk.py` for the entry gate. Record your finding.

## Output / deliverables
1. Modified recommendation_api.py
2. Brief written rationale for (a) vs (b) choice
3. Log sample showing before/after noise level
4. Result JSON at `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_REGISTRY_PREGAME_WINDOW_001.json`

## Result JSON fields required
```json
{
  "task_id": "REGISTRY_PREGAME_WINDOW_001",
  "status": "ok",
  "option_chosen": "b",
  "rationale": "...",
  "bot_pregame_trading_verified": false,
  "log_lines_before_sample": ["..."],
  "log_lines_after_sample": ["..."],
  "files_changed": ["..."]
}
```

## Do NOT do
- Do not change the bot's entry gate (whether it trades pre-game or not)
- Do not change the registry data source
- Do not change the recommendation_api's matching logic for same-day events
- Do not rename anything (that's SHADOW_ENGINE_RENAME_001)
- Do not modify BOT_BRIDGE contents
- No real-money paths

---
## RETRY CONTEXT (auto-generated — attempt 3)

A previous run failed on this task. Before you start, read this:

- prior status: `fail`
- prior summary: (no RESULT_JSON emitted and no RESULT file written)
- prior run id: `RUN_35E9E0C36590`

### What went wrong
The previous worker did not produce a RESULT for **REGISTRY_PREGAME_WINDOW_001**. Common causes: (a) the worker drifted to a different task, (b) the worker never wrote `RESULT_REGISTRY_PREGAME_WINDOW_001.json`, (c) the worker exited before completing the scope.

### What to do differently this attempt
1. Work ONLY on `REGISTRY_PREGAME_WINDOW_001`. Ignore every other task name you see.
2. Write your result to `BOT_BRIDGE/06_OUTBOX_FROM_WORKER/RESULT_REGISTRY_PREGAME_WINDOW_001.json` and NO other file.
3. If the scope is unclear, emit `status: blocked` with a specific question.
   Do NOT substitute a different task you think you know.

### Prior stdout tail (for diagnosis)
```
- **Before**: ~40 verbose `no_registry_match` logs per run with full registry dumps → pollutes logs, masks real issues
- **After**: 0 verbose logs, replaced with 1 summary count + 1 event list line
- No change to same-day event matching or bot entry gates
- Registry window semantics unchanged (still holds today only)

## Result File

Written to: `C:\Users\johnny\Desktop\mlbbot\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_REGISTRY_PREGAME_WINDOW_001.json`

Status: `ok` ✓
[done] ok duration=77713ms turns=8
[usage] input=66 output=6419 cache_read=387789 cost_usd=0.1068
```
