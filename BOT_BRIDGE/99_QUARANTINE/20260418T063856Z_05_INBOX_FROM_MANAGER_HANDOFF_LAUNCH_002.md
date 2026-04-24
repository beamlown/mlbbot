# HANDOFF — LAUNCH_002
## Add dashboard_server.py to launch_all.py managed process list

---

## Context

`dashboard_server.py` is currently started manually and has no PID guard. Every separate `python dashboard_server.py` call adds a new unguarded instance. The fix is to add it to the `PROCESSES` list in `launch_all.py` — the existing watchdog and singleton PID guard then cover it automatically.

---

## File to change

`sports_bot_v2/launch_all.py` — ONLY this file.

---

## Exact change

Find the `PROCESSES` list (lines 20–33). It currently has two entries.

**Add a third entry at the end of the list, before the closing `]`:**

```python
    {
        "name": "dashboard",
        "command": [sys.executable, "dashboard_server.py"],
        "cwd": str(SPORTS_BOT_DIR),
        "log_file": str(LOG_DIR / "dashboard.log"),
    },
```

The full list after the change:

```python
PROCESSES = [
    {
        "name": "shadow_engine",
        "command": [sys.executable, "-m", "integration.recommendation_api"],
        "cwd": str(MLB_MODEL_DIR),
        "log_file": str(LOG_DIR / "shadow_engine.log"),
    },
    {
        "name": "bot_core",
        "command": [sys.executable, "bot_core.py"],
        "cwd": str(SPORTS_BOT_DIR),
        "log_file": str(LOG_DIR / "bot_core_launcher.log"),
    },
    {
        "name": "dashboard",
        "command": [sys.executable, "dashboard_server.py"],
        "cwd": str(SPORTS_BOT_DIR),
        "log_file": str(LOG_DIR / "dashboard.log"),
    },
]
```

No other changes.

---

## Verification

```
cd C:\Users\johnny\Desktop\sports_bot_v2
python launch_all.py
```

Expected output:
```
LAUNCHER: shadow_engine started (pid=XXXXX, attempt=1)
LAUNCHER: bot_core started (pid=XXXXX, attempt=1)
LAUNCHER: dashboard started (pid=XXXXX, attempt=1)
```

Then in a second terminal (while first is still running):
```
python launch_all.py
```

Must print: `ERROR: launcher already running at PID XXXXX. Stop it first.`

Stop the launcher with Ctrl-C after verification.

## Rollback

Revert `launch_all.py` only.
