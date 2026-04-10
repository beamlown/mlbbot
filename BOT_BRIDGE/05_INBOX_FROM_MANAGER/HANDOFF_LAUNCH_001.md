# Worker Handoff Note — LAUNCH_001
## Created: 2026-04-04

---

## What this task is

Two narrow changes:

1. **New file: `launch_all.py`** — starts both the shadow engine and the bot concurrently, keeps both alive with a simple watchdog loop.
2. **`core/model_bridge.py` — one log line** — when there are no actionable candidates after dedup, log `BRIDGE ALL STALE` instead of returning silently.

---

## Task brief location

`C:\Users\johnny\Desktop\BOT_BRIDGE\05_INBOX_FROM_MANAGER\TASK_LAUNCH_001.json`

---

## Files you may touch

```
C:\Users\johnny\Desktop\sports_bot_v2\launch_all.py       ← NEW file
C:\Users\johnny\Desktop\sports_bot_v2\core\model_bridge.py ← one log line addition
```

Do not touch anything else.

---

## 1. `launch_all.py` — what to build

A simple supervisor script. No threading, no asyncio — just `subprocess.Popen` and a polling loop.

```python
# Suggested structure

import subprocess
import time
import sys
import signal

RESTART_DELAY = 5    # seconds before restarting a dead process
POLL_INTERVAL = 10   # seconds between health checks

PROCESSES = [
    {
        "name": "shadow_engine",
        "cmd": [sys.executable, "-m", "integration.recommendation_api"],
        "cwd": r"C:\Users\johnny\Desktop\mlb_model",
        "log": r"C:\Users\johnny\Desktop\sports_bot_v2\logs\shadow_engine.log",
    },
    {
        "name": "bot_core",
        "cmd": [sys.executable, "bot_core.py"],
        "cwd": r"C:\Users\johnny\Desktop\sports_bot_v2",
        "log": r"C:\Users\johnny\Desktop\sports_bot_v2\logs\bot_core_launcher.log",
    },
]
```

**Main loop logic:**

```python
def start_process(spec, attempt=1):
    log_fh = open(spec["log"], "a")
    proc = subprocess.Popen(
        spec["cmd"],
        cwd=spec["cwd"],
        stdout=log_fh,
        stderr=log_fh,
    )
    print(f"LAUNCHER: {spec['name']} started (pid={proc.pid}, attempt={attempt})")
    return proc, log_fh

# Start both
procs = {spec["name"]: {"proc": p, "fh": fh, "spec": spec, "attempt": 1}
         for spec in PROCESSES for p, fh in [start_process(spec)]}

# Watchdog loop
try:
    while True:
        time.sleep(POLL_INTERVAL)
        for name, entry in procs.items():
            rc = entry["proc"].poll()
            if rc is not None:
                entry["fh"].close()
                print(f"LAUNCHER: {name} exited (code={rc}) — restarting in {RESTART_DELAY}s")
                time.sleep(RESTART_DELAY)
                entry["attempt"] += 1
                entry["proc"], entry["fh"] = start_process(entry["spec"], entry["attempt"])
                print(f"LAUNCHER: {name} restarted (attempt {entry['attempt']})")
except KeyboardInterrupt:
    print("LAUNCHER: shutting down...")
    for entry in procs.values():
        entry["proc"].terminate()
        entry["fh"].close()
    print("LAUNCHER: all processes terminated.")
```

This is the complete structure. Adapt as needed — keep it simple.

---

## 2. `core/model_bridge.py` — one addition

Find the point in `get_approved_intents()` where, after dedup and NO_TRADE filtering, the working set is empty (no actionable candidates). Currently it returns `[]` silently.

Replace that silent return with:

```python
if not working_set:
    logger.info(
        "BRIDGE ALL STALE — no actionable recommendations found; "
        "shadow engine may not be running or all recs are stale"
    )
    return []
```

One log line. Nothing else changes.

---

## Why this solves the stale problem

Before this task: the shadow engine and bot were run separately. By the time the bot's bridge checked the log, recommendations were hours old → all `rec_age` rejections.

After this task: `launch_all.py` starts both processes at the same time. The shadow engine produces fresh recommendations every ~30s. The bridge reads them within 120s of creation → `rec_age` gate passes → `BRIDGE GATE PASS` observed.

---

## How to verify

```
cd C:\Users\johnny\Desktop\sports_bot_v2
python launch_all.py
```

Watch for:
- `LAUNCHER: shadow_engine started (pid=...)`
- `LAUNCHER: bot_core started (pid=...)`
- Shadow engine logs appearing in `logs/shadow_engine.log`
- Bot logs appearing in `logs/bot_core_launcher.log`
- After ~2 loops: `BRIDGE GATE REJECT` lines (normal until a qualifying rec arrives)
- If no fresh recs yet: `BRIDGE ALL STALE` visible in bot log
- Once shadow engine has run 1-2 loops: `BRIDGE GATE REJECT [rec_age]` lines should have ages < 120s — or better, a `BRIDGE GATE PASS`

**To test watchdog:** In a second terminal, kill the shadow_engine process manually (`taskkill /PID <pid> /F` on Windows). The launcher should log the exit and restart it within `RESTART_DELAY` seconds.

---

## How to deliver

```
C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_LAUNCH_001.json
```

Include:
- `files_changed`: `["launch_all.py", "core/model_bridge.py"]`
- `summary`
- `commands_run`
- `tests_run`: describe what you observed in launcher logs
- `watchdog_tested`: did you test the restart behavior? what happened?
- `bridge_all_stale_observed`: did the BRIDGE ALL STALE log line appear?
- `gate_reject_ages`: what rec_age values did you see once both were running?
- `gate_pass_observed`: yes/no
- `risks`
- `next_recommended_task`

---

## Rollback

Delete `launch_all.py`. Revert `core/model_bridge.py`. Both processes can still be run manually as before.
