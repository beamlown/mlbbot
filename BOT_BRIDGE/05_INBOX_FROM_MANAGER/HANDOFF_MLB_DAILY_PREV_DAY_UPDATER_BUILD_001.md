# HANDOFF: MLB_DAILY_PREV_DAY_UPDATER_BUILD_001

## Status
QUEUED — reassigned to SONNET_WORKER (HAIKU_WORKER failed to produce output on two prior attempts; prior brief was too sparse)

## What you are doing
Create `C:\Users\johnny\Desktop\mlb_model\scripts\update_prev_day.py` — a daily
previous-day ingestion script that appends yesterday's completed MLB games to
the canonical store.

## Why this script exists
The season backfill (`backfill_season.py`) wrote 2026-03-25 through 2026-04-16.
Once the season is underway, a daily job runs each morning to fetch the prior
day's completed games and write them into the same store. This script is that job.

## Canonical store location
```
C:\Users\johnny\Desktop\mlb_model\data\foundation\mlb_statsapi\season=2026\
  raw\
    games\game_date=YYYY-MM-DD\games.jsonl
    teams\game_date=season\teams.jsonl
    team_game_logs\game_date=YYYY-MM-DD\team_game_logs.jsonl
    pitcher_game_logs\game_date=YYYY-MM-DD\pitcher_game_logs.jsonl
    bullpen_context\game_date=YYYY-MM-DD\bullpen_context.jsonl
    game_state_history\game_date=YYYY-MM-DD\game_state_history.jsonl
  normalized\
    games\game_date=YYYY-MM-DD\games.jsonl
    team_game_logs\game_date=YYYY-MM-DD\team_game_logs.jsonl
    pitcher_game_logs\game_date=YYYY-MM-DD\pitcher_game_logs.jsonl
    game_state_features\game_date=YYYY-MM-DD\game_state_features.jsonl
  manifests\
    daily_YYYYMMDD.json
```

## Reference implementation
`backfill_season.py` (same directory) contains ALL the API helpers, entity
builders, and write utilities you should reuse exactly:
- `api_get`, `fetch_schedule`, `fetch_boxscore`, `fetch_linescore`, `fetch_teams`
- `build_raw_game`, `build_pitcher_game_logs`, `build_team_game_logs`,
  `build_bullpen_context`, `build_game_state_history`, `build_raw_teams`
- `build_normalized_*` functions
- `write_jsonl`, `_ip_str_to_float`, `CANONICAL_ROOT / RAW_ROOT / NORM_ROOT / MANIFESTS_ROOT`
- `SESSION` (requests.Session with User-Agent header)

Do NOT duplicate this logic. Import from `backfill_season` or copy only what
you cannot import (since it's a script, not a module — copy the minimal needed
helpers if a shared import is awkward, but prefer to keep it DRY).

## Key differences from backfill_season.py

| Concern | backfill_season.py | update_prev_day.py |
|---------|-------------------|-------------------|
| Target date(s) | date range (loop) | single date = yesterday |
| Date override | `--start-date` / `--end-date` | `--date YYYY-MM-DD` (default: yesterday) |
| Idempotency | **skip-if-exists** (skip if partition non-empty) | **atomic replace** (always refetch; write to .tmp dirs, validate, rename) |
| Manifest type | `backfill_YYYYMMDD.json` | `daily_YYYYMMDD.json` |
| Teams | write only if absent | write only if absent (same rule) |

## Idempotency / atomic replace behavior
The foundation spec requires daily updater to use atomic replace, not skip-if-exists.
Implementation:
1. Compute all target partition paths for the date.
2. Write each entity to a sibling `.tmp` directory first
   (e.g. `raw/games/game_date=2026-04-17.tmp/`).
3. After all entities are written successfully, validate counts (games > 0,
   team_game_logs == 2 * games, etc.).
4. On validation pass: for each entity, delete existing live partition if
   present, then rename `.tmp` → live partition name.
5. On validation fail or any write error: delete all `.tmp` dirs and exit non-zero.
6. Write manifest only after all renames succeed.

This means the script is safe to rerun: a failed or partial prior run leaves
`.tmp` dirs (clean them up automatically at script start) or no dirs at all.
Cleanup of stale `.tmp` dirs: at startup, if any `.tmp` sibling dirs exist for
this date, remove them before starting fresh.

## Validation rules
After writing to `.tmp`, validate:
- `len(raw_games) > 0` — must have at least one game
- `len(raw_tgl) == 2 * len(raw_games)` — exactly 2 team logs per game
- `len(raw_pgl) > 0` — at least some pitchers
- `len(raw_bc) == 2 * len(raw_games)` — exactly 2 bullpen context rows per game

## CLI interface
```
python update_prev_day.py [--date YYYY-MM-DD]
```
- `--date`: target game date (default: yesterday, i.e. `date.today() - timedelta(days=1)`)
- Safety clamp: if `--date` is today or future, exit with error (never process in-progress games)

## Output / deliverables
1. Script file: `C:\Users\johnny\Desktop\mlb_model\scripts\update_prev_day.py`
2. Manifest written on success: `manifests\daily_YYYYMMDD.json` where YYYYMMDD = run date (today)
3. Result JSON written to: `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_MLB_DAILY_PREV_DAY_UPDATER_BUILD_001.json`

## Result JSON fields required
```json
{
  "task_id": "MLB_DAILY_PREV_DAY_UPDATER_BUILD_001",
  "status": "ok",
  "script_path": "...",
  "target_date_behavior": "yesterday by default, overridable via --date",
  "idempotency_behavior": "atomic replace: write .tmp → validate → rename live; stale .tmp cleanup on startup",
  "append_target_paths": [ "...raw/games/game_date=YYYY-MM-DD/games.jsonl", "..." ],
  "manifest_path_pattern": "manifests/daily_YYYYMMDD.json",
  "compatibility_with_backfill": "...",
  "files_changed": [ "..." ]
}
```

## Do NOT do
- No model/recommendation changes
- No storage redesign or schema changes
- No scheduling/cron/platform work
- Do not touch `backfill_season.py` unless there is a genuine shared-helper extraction
- Do not process today's date (in-progress games)
