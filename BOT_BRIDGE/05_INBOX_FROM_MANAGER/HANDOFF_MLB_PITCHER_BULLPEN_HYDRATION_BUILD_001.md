# HANDOFF: MLB_PITCHER_BULLPEN_HYDRATION_BUILD_001
**RE-ISSUED 2026-04-17 — FOURTH attempt. Prior runs all SIGKILLed. SINGLE-GAME PROOF RUN ONLY.**

## Context

Three prior runs were all killed mid-execution. The worker must not attempt to iterate more than one game's worth of data in this run.

## What you are doing THIS run

This is a PROOF RUN only. Fetch pitcher data for exactly ONE game and write one row to pitcher_game_logs. Nothing else.

**Hard limit: fetch exactly 1 game_pk. Write exactly 1 row. Exit.**

## Goal for this run
1. Pick any one completed game_pk from 2026-03-25 to 2026-04-11
2. Fetch its boxscore from MLB Stats API
3. Extract starter + relief pitcher data
4. Write that single game's pitcher_game_logs row to the canonical partition
5. Write the result JSON and STOP

Do NOT loop. Do NOT try to process multiple games. Do NOT run any existing batch script unless you can confirm it only touches 1 game.

If this single game proves the write path works, manager will re-issue for batches of 10.

## Authoritative boundary
- Start: 2026-03-25
- End: 2026-04-11
- Games available: ~221 completed games (but you are only writing 1 today)

## Source confirmed available
MLB Stats API boxscore endpoint contains pitcher lists. No source-availability problem.

The manager will re-issue for the next batch once the first slice is confirmed written.

## After pitcher_game_logs is populated
Derive bullpen_context (relief appearances, handedness, fatigue indicators) from pitcher_game_logs in a separate batch pass.

## Allowed files
```
C:\Users\johnny\Desktop\mlb_model\scripts\**
C:\Users\johnny\Desktop\mlb_model\data\foundation\mlb_statsapi\season=2026\**
C:\Users\johnny\Desktop\BOT_BRIDGE\08_SHARED_CONTEXT\MLB_STATS_FOUNDATION_SPEC_001.md
C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_MLB_CURRENT_SEASON_BACKFILL_BUILD_001.json
C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_MLB_BACKFILL_HYDRATION_GAP_FIX_001.json
```

## Deliver back
- exact date range or team slice processed
- number of pitcher_game_logs rows written
- number of bullpen_context rows written (if derived)
- any games where pitcher data was unavailable from API
- py_compile or import check (if any script was modified)

## Do not do
- no full-season iteration in a single process
- no daily updater work
- no model/recommendation code
- no storage redesign
