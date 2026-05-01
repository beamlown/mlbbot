# HANDOFF — LAUNCH_FIX_001B
## Fix PID guard in launch_all.py — absolute path + ctypes liveness check

---

## Why 001 failed

Two bugs in the LAUNCH_FIX_001 implementation:

1. **`LAUNCHER_PID_FILE = Path("runtime/launcher.pid")` is relative to CWD.** If two terminals have different working directories, they write to different files. Guard never fires.

2. **`os.kill(pid, 0)` on Windows can raise `PermissionError`** (which is an `OSError` subclass) even when the target process IS running. The `except (OSError, ValueError): pass` then treats a live launcher as dead and lets the second instance through.

---

## File to change

`sports_bot_v2/launch_all.py` — ONLY this file.

---

## Exact changes

### Change 1 — Fix the constant block (top of file, lines 1–18)

**Replace:**
```python
RESTART_DELAY_SECONDS = 5
POLL_INTERVAL_SECONDS = 10
LAUNCHER_PID_FILE = Path("runtime/launcher.pid")

SPORTS_BOT_DIR = Path(__file__).resolve().parent
MLB_MODEL_DIR = SPORTS_BOT_DIR.parent / "mlb_model"
LOG_DIR = SPORTS_BOT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
```

**With:**
```python
import ctypes

RESTART_DELAY_SECONDS = 5
POLL_INTERVAL_SECONDS = 10

SPORTS_BOT_DIR = Path(__file__).resolve().parent
LAUNCHER_PID_FILE = SPORTS_BOT_DIR / "runtime" / "launcher.pid"  # absolute path
MLB_MODEL_DIR = SPORTS_BOT_DIR.parent / "mlb_model"
LOG_DIR = SPORTS_BOT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
```

Key changes: `import ctypes` added; `SPORTS_BOT_DIR` moved before `LAUNCHER_PID_FILE`; path is now absolute.

---

### Change 2 — Add `_pid_is_running()` helper before `main()`

Add this function just before `def main():`:

```python
def _pid_is_running(pid: int) -> bool:
    """Windows-reliable process liveness check via OpenProcess."""
    PROCESS_QUERY_INFORMATION = 0x0400
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
    if not handle:
        return False
    ctypes.windll.kernel32.CloseHandle(handle)
    return True
```

Why this works: `OpenProcess(PROCESS_QUERY_INFORMATION, ...)` only needs the process to exist — not to be owned by us. Returns NULL (0/falsy) only if the PID does not exist. No permission issues.

---

### Change 3 — Replace the PID guard in `main()`

**Replace:**
```python
def main() -> None:
    if LAUNCHER_PID_FILE.exists():
        try:
            old_pid = int(LAUNCHER_PID_FILE.read_text(encoding="utf-8").strip())
            os.kill(old_pid, 0)
            print(f"ERROR: launcher already running at PID {old_pid}. Stop it first.", flush=True)
            sys.exit(1)
        except (OSError, ValueError):
            pass
```

**With:**
```python
def main() -> None:
    if LAUNCHER_PID_FILE.exists():
        try:
            old_pid = int(LAUNCHER_PID_FILE.read_text(encoding="utf-8").strip())
            if _pid_is_running(old_pid):
                print(f"ERROR: launcher already running at PID {old_pid}. Stop it first.", flush=True)
                sys.exit(1)
        except ValueError:
            pass  # corrupt PID file — overwrite it
```

Key change: `os.kill` replaced with `_pid_is_running()`; `OSError` removed from except (only `ValueError` for corrupt file content).

---

## What stays the same

- `start_process()` — unchanged
- `stop_process()` — unchanged
- Watchdog loop — unchanged
- Signal handlers — unchanged
- `finally: LAUNCHER_PID_FILE.unlink(missing_ok=True)` — already correct, keep it

---

## Verification

Run from **two different working directories** to catch the path bug:

```
# Terminal 1 (from project dir):
cd C:\Users\johnny\Desktop\sports_bot_v2
python launch_all.py
# → should start, print LAUNCHER: shadow_engine started, LAUNCHER: bot_core started

# Terminal 2 (from a DIFFERENT dir — this is the test):
cd C:\Users\johnny
python C:\Users\johnny\Desktop\sports_bot_v2\launch_all.py
# → should print: ERROR: launcher already running at PID <N>. Stop it first.
# → and exit immediately (no child processes spawned)

# Ctrl+C Terminal 1
# → runtime/launcher.pid should be gone

# Terminal 1 again:
python launch_all.py
# → should start normally
```

## Rollback

Revert `launch_all.py` only.
