# HANDOFF — LAUNCH_FIX_001
## Add PID guard to launch_all.py to prevent duplicate launcher instances

---

## Context

On 2026-04-04, `launch_all.py` was run multiple times without stopping the previous instance. Each run spawned additional bot_core.py and recommendation_api.py processes. The watchdog inside each launcher also independently restarted crashed children on top of surviving ones. Peak: 6 bot_core.py + 3 launch_all.py + 10 recommendation_api.py processes simultaneously.

Fix: write a PID file on startup (`runtime/launcher.pid`). If a launcher PID file exists AND that process is still alive, refuse to start.

---

## File to change

`sports_bot_v2/launch_all.py` — ONLY this file.

---

## Exact changes

### 1. Add constant near top of file (after imports):
```python
LAUNCHER_PID_FILE = Path("runtime/launcher.pid")
```

### 2. Add PID guard at the very start of `main()` (before any subprocess spawning):
```python
# Prevent duplicate launcher instances
if LAUNCHER_PID_FILE.exists():
    try:
        old_pid = int(LAUNCHER_PID_FILE.read_text().strip())
        os.kill(old_pid, 0)  # raises OSError if process is not running
        print(f"ERROR: launcher already running at PID {old_pid}. Stop it first.")
        sys.exit(1)
    except (OSError, ValueError):
        pass  # old PID is dead (crash/reboot) — safe to continue
LAUNCHER_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
LAUNCHER_PID_FILE.write_text(str(os.getpid()))
```

### 3. Add cleanup in the finally/exit block:
```python
LAUNCHER_PID_FILE.unlink(missing_ok=True)
```

If `launch_all.py` doesn't already have a `try/finally`, wrap the main watchdog loop:
```python
try:
    # ... existing watchdog loop ...
finally:
    LAUNCHER_PID_FILE.unlink(missing_ok=True)
    # ... any existing cleanup ...
```

---

## Notes

- `os.kill(pid, 0)` on Windows raises `OSError` if the process does not exist — this is the correct cross-platform liveness check.
- `missing_ok=True` on `Path.unlink()` is Python 3.8+ — fine for this project.
- `runtime/` directory already exists (bot_core.py writes `runtime/bot.pid` there).
- Do NOT change subprocess commands, watchdog poll interval, log file paths, or any other logic.

---

## Verification

1. Start `python launch_all.py` — confirm `runtime/launcher.pid` is written
2. In a second terminal: `python launch_all.py` — should print error and exit immediately (no children spawned)
3. Ctrl+C the first launcher — confirm `runtime/launcher.pid` is removed
4. Re-run `python launch_all.py` — should start normally

## Rollback

Revert `launch_all.py` only.
