# REVIEW_SINGLE_STACK_LAUNCH_GUARD_001.md

## Verdict
APPROVED

## Decision
Approve `SINGLE_STACK_LAUNCH_GUARD_001`. Move to DONE.

## What was confirmed

- Only `launch_all.py` modified.
- Strategy chosen: post-sweep bot.pid check — secondary guard that verifies bot_core is fully dead after `sweep_stale_processes()`.
- Uses existing `_pid_is_running()` helper (Windows `OpenProcess`) — no new dependencies added.
- Guard fires only if `runtime/bot.pid` exists AND the recorded PID is still running after sweep.
- On conflict: `sys.exit(1)` with error message including the exact elevated kill command the operator needs.
- Normal launch (no stale process, or sweep successfully killed it) is completely unaffected.
- `python -m py_compile launch_all.py` — PASS.
- No runtime restart needed — guard applies on next launch.

## Why this matters

Tonight's dual-stack confusion happened because the original 4:25 PM stack ran under elevated permissions and could not be killed by non-elevated `Stop-Process`. The launcher's existing sweep silently failed and the new launcher still started, creating two concurrent bot_cores writing to different log files. Now the second launch attempt will abort with a clear error pointing the operator to the right kill command.

## File locks released

- `launch_all.py` — RELEASED

## Manager judgment

Close `SINGLE_STACK_LAUNCH_GUARD_001` to DONE.
