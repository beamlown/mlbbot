# REVIEW — DASHBOARD_LIVE_ATBAT_POLISH_001
**Reviewed by:** Claude (manager)
**Date:** 2026-04-10
**Verdict:** PROVISIONAL PASS — follow-on task documented

---

## Summary

Dashboard upgrade: live game cards now show dominant score hierarchy (38px runs, team names, green leader highlight), TOP/BOT inning notation, color-coded count chips (blue/gold/gray dots for balls/strikes/outs), current batter and pitcher identity, and last-play text. Position card game state row condensed from 6-stat grid to 3-stat + count chips.

Files changed: `dashboard.html`, `dashboard_server.py` (2 lines in `_build_games_from_raw` to expose `current_batter` and `current_pitcher`).

---

## Acceptance Criteria Check

| Criterion | Result |
|-----------|--------|
| Score/inning/outs/count readable at a glance | PASS — 38px dominant score, count chips |
| Current batter visually obvious | PASS (conditional — shown if ESPN situation provides batter; gracefully absent if not) |
| Next-three-up | NOT IMPLEMENTED — data not available in current ESPN scoreboard path |
| Runner base state easier to read | PASS — diamond unchanged, runner text retained |
| Prettier and more readable | PASS — score dominant, visual hierarchy clear |
| No unrelated components touched | PASS |
| No bot/risk/process behavior changed | PASS — dashboard only |

---

## next_three_up Assessment

Worker correctly identified that the ESPN scoreboard `situation` object does not include batting lineup order. Next-batters data would require parsing the ESPN `summary/detail` endpoint, which is not currently wired. Worker documented this as `TASK_NEXT_BATTERS_ENRICH_001` with clear scope. This is acceptable — the task brief listed it as a goal, not a hard requirement, and the data simply is not available in the current path.

---

## Restart Note

`restart_needed: false` per worker. However: `dashboard_server.py` was modified. If the dashboard server process is not running in Flask debug/reloader mode, a supervisor restart of the dashboard_server.py process is needed for `current_batter` and `current_pitcher` fields to be served. Bot and risk processes are unaffected.

---

## Decision

**PROVISIONAL PASS** — all achievable criteria met; next_three_up correctly scoped to a follow-on task. No changes requested. Follow-on task `TASK_NEXT_BATTERS_ENRICH_001` may be queued when bandwidth allows.
