# REVIEW_EXIT_GAME_AWARE_001

**Decision: BLOCKED**
**Reviewed: 2026-04-10**

---

## What passed

- Scope respected: only `bot_core.py` was modified ✓
- Code structure matched the brief spec: gate inserted before `check_exit`, `continue` on FINAL+winning, fallthrough on losing or unknown ✓
- Import extended to include `NEAR_RESOLUTION_PRICE` from `core/risk.py` ✓
- Rollback is possible via `git revert` ✓

---

## What failed

### CRITICAL — False premise: `resolution_watcher` does not exist

The task brief states:

> "resolution_watcher.py already runs as a process and closes settled markets."

This is **incorrect**. The `integration/` directory does not exist in the project. `launch_all.py` references `integration.resolution_watcher` as a subprocess, but the module was never created. There is no process to close HOLD_TO_RESOLUTION positions.

### CRITICAL — Production harm observed

The HOLD_TO_RESOLUTION gate was deployed and caused **three trades to become permanently stuck** in production:

| id | slug | side | status |
|----|------|------|--------|
| 200 | mlb-cws-kc-2026-04-11 | BUY_YES | stuck open |
| 205 | mlb-cws-kc-2026-04-10 | BUY_NO | stuck open |
| 213 | mlb-col-sd-2026-04-09 | BUY_YES | stuck open |

Games ended. Prices moved above `NEAR_RESOLUTION_PRICE`. Bot logged `HOLD_TO_RESOLUTION` every loop and did nothing. All three required **manual DB remediation** (UPDATE trades SET status='closed' WHERE id IN (200, 205, 213)).

### Verification insufficient

Result listed verification steps but provided no actual output showing them run. The critical simulation step ("manually set game status to FINAL, confirm HOLD_TO_RESOLUTION log and no close") was not performed.

---

## Current state

The HOLD_TO_RESOLUTION gate has been **removed from `bot_core.py`** in the same session as the stuck-trade remediation. `check_exit` now runs unconditionally for all open trades. The `near_resolution` exit in `risk.py` (line 188) handles winning positions cleanly at ≥ 0.92 without needing a separate watcher process.

---

## What must happen before this feature can be reconsidered

1. `integration/resolution_watcher.py` must be built and verified running
2. End-to-end test: gate holds trade → watcher closes at 1.00 → confirmed in DB
3. Only then should a revised EXIT_GAME_AWARE_002 be written

Until then, `check_exit` near_resolution is the correct and safe exit path for winning FINAL positions.

---

## Next action

- Do NOT re-implement this gate without resolution_watcher in place
- Mark EXIT_GAME_AWARE_001 BLOCKED on board
- No follow-up task to be written at this time
