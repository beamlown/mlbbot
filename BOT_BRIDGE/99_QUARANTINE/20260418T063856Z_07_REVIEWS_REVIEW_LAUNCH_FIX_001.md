# REVIEW_LAUNCH_FIX_001

Decision: BLOCKED

## What passed
- Scope stayed inside `launch_all.py` only.
- PID guard logic is structurally correct (check → verify alive → write → proceed).
- Cleanup in `finally` block is correct.
- Worker correctly self-identified failure and did not claim completion.

## What failed
- Verification failed: second `python launch_all.py` started normally instead of exiting.

## Root cause (identified by manager code read)

**Bug 1 — Relative path resolves against CWD, not script location (line 12):**
```python
LAUNCHER_PID_FILE = Path("runtime/launcher.pid")  # ← relative to wherever python is run from
```
If the user runs both launchers from different terminal working directories, each instance writes/reads a different physical file. Launcher 2 never sees Launcher 1's PID file and starts cleanly.

`SPORTS_BOT_DIR = Path(__file__).resolve().parent` is defined two lines later (line 14) and IS the correct anchor — but `LAUNCHER_PID_FILE` is defined before it and can't reference it.

**Bug 2 — `os.kill(pid, 0)` on Windows swallows a live process as dead:**
On Windows, `os.kill(pid, 0)` may call `OpenProcess(PROCESS_ALL_ACCESS, ...)`. If the running process is owned by the same user but `PROCESS_ALL_ACCESS` is denied for any reason, it raises `PermissionError` — which IS a subclass of `OSError`. The `except (OSError, ValueError): pass` then silently treats the live launcher as dead and proceeds to start. So even if the path issue is fixed, this gate can fail.

## Notes
- Superseded by LAUNCH_FIX_001B, which provides the specific Windows-compatible fix.
- Do NOT merge the current launch_all.py changes — the guard is non-functional.

## Next action
- Revert launch_all.py changes from this attempt OR apply targeted fixes in LAUNCH_FIX_001B.
- LAUNCH_FIX_001B is written to 05_INBOX_FROM_MANAGER.
