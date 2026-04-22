# REVIEW_LAUNCH_FIX_001B

Decision: APPROVED

## What passed
- Scope: only `launch_all.py` modified.
- **Bug 1 fixed** — `LAUNCHER_PID_FILE` is now absolute (line 15): `SPORTS_BOT_DIR / "runtime" / "launcher.pid"`. `SPORTS_BOT_DIR` correctly defined first (line 14). Path is immune to CWD differences between terminal sessions.
- **Bug 2 fixed** — `os.kill` replaced with `_pid_is_running()` (lines 61–68) using `ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, ...)`. Returns `False` only when process genuinely does not exist; no permission-related false negatives.
- `except` clause now catches only `ValueError` (corrupt PID file content), not `OSError` — prevents the original swallow-the-live-process bug.
- `finally: LAUNCHER_PID_FILE.unlink(missing_ok=True)` present (line 119) — cleanup on exit.
- All other logic unchanged: `start_process`, `stop_process`, watchdog loop, signal handlers.
- Worker confirmed verification passed (second launcher correctly blocked).
- Rollback: revert `launch_all.py` only. ✓

## What failed
- none

## Notes
- `ctypes` is stdlib — no new dependency.
- The `_pid_is_running` function is Windows-specific (`ctypes.windll`). Acceptable: the project runs on Windows 11.

## Next action
- Update task board: LAUNCH_FIX_001B → DONE, unlock `launch_all.py`.
- BRIDGE_FIX_001 is also approved (reviewed separately). Once both are on the board as DONE, the bridge re-enable gate is clear: set `ENABLE_MODEL_BRIDGE = True` in `core/model_bridge.py` and run one controlled session via `launch_all.py`.
