# HANDOFF — VERIFY_STABILIZE_001
## Fix stale shadow ghost positions — resolution_watcher + dashboard date guard

---

## Context

The dashboard unified positions panel currently shows **12 ghost SHADOW cards** from yesterday's (2026-04-04) completed games, all labelled OPEN with stale PnL estimates. Two bugs cause this:

1. **`resolution_watcher` is not running.** It was killed during a process cleanup on 2026-04-05 and was never added to `launch_all.py`. Without it, entries in `shadow_recommendations.jsonl` never get their `resolved` field set to `True`. The dashboard filter (`!r.resolved`) therefore includes all past-day entries forever.

2. **`dashboard_server.py` has no date guard.** `_read_mlb_shadow()` loads all recs from the jsonl file and passes them to the frontend with no date filter. Stale past-day recs accumulate indefinitely.

---

## Files to change

- `sports_bot_v2/launch_all.py` — add resolution_watcher as 4th managed process
- `sports_bot_v2/dashboard_server.py` — add date guard in `_read_mlb_shadow()`

Do NOT touch: `dashboard.html`, `bot_core.py`, `core/`, `mlb_model/` source files.

---

## Change 1 — launch_all.py

Find the `PROCESSES` list. It currently has 3 entries: `shadow_engine`, `bot_core`, `dashboard`.

**Add a 4th entry at the end of the list:**

```python
    {
        "name": "resolution_watcher",
        "command": [sys.executable, "-m", "integration.resolution_watcher"],
        "cwd": str(MLB_MODEL_DIR),
        "log_file": str(LOG_DIR / "resolution_watcher.log"),
    },
```

`MLB_MODEL_DIR` is already defined as `SPORTS_BOT_DIR.parent / "mlb_model"`. No other changes needed.

The full PROCESSES list after the change:

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
    {
        "name": "resolution_watcher",
        "command": [sys.executable, "-m", "integration.resolution_watcher"],
        "cwd": str(MLB_MODEL_DIR),
        "log_file": str(LOG_DIR / "resolution_watcher.log"),
    },
]
```

---

## Change 2 — dashboard_server.py

Find `_read_mlb_shadow()`. It loads recs from `shadow_recommendations.jsonl` and returns them.

**After loading the recs list, add a date filter before any other processing:**

```python
from datetime import date as _date

def _read_mlb_shadow(limit: int = 50) -> dict:
    ...
    # (existing code to load recs from jsonl) ...

    # --- ADD THIS BLOCK after recs are loaded, before sorting/slicing ---
    today_str = _date.today().isoformat()  # e.g. "2026-04-05"
    def _slug_is_today_or_newer(slug: str) -> bool:
        # slug format: mlb-TEAM-TEAM-YYYY-MM-DD
        parts = slug.rsplit("-", 3)
        if len(parts) == 4:
            try:
                slug_date = f"{parts[1]}-{parts[2]}-{parts[3]}"
                return slug_date >= today_str
            except Exception:
                return True  # fail open — include if unparseable
        return True
    recs = [r for r in recs if _slug_is_today_or_newer(r.get("market_slug", ""))]
    # --- END ADDED BLOCK ---

    # (existing sort/slice/return logic continues unchanged)
```

**Important:** The slug format for a game like `mlb-sea-laa-2026-04-04` ends in `YYYY-MM-DD`. The `rsplit("-", 3)` splits from the right into at most 4 parts: `["mlb-sea-laa", "2026", "04", "04"]`. Reconstruct as `"2026-04-04"` and compare to today.

---

## Verification

Stop any running launcher first (Ctrl-C or kill PIDs). Then:

```
cd C:\Users\johnny\Desktop\sports_bot_v2
python launch_all.py
```

Expected output (4 LAUNCHER lines):
```
LAUNCHER: shadow_engine started (pid=XXXXX, attempt=1)
LAUNCHER: bot_core started (pid=XXXXX, attempt=1)
LAUNCHER: dashboard started (pid=XXXXX, attempt=1)
LAUNCHER: resolution_watcher started (pid=XXXXX, attempt=1)
```

Then verify the date filter:
```
python -c "import requests; recs=requests.get('http://localhost:8900/api/mlb-shadow').json().get('recs',[]); stale=[r for r in recs if '2026-04-04' in r.get('market_slug','')]; print('stale recs:', len(stale))"
```

Expected: `stale recs: 0`

Second launcher attempt must still show: `ERROR: launcher already running at PID XXXXX. Stop it first.`

---

## Rollback

Revert `launch_all.py` and `dashboard_server.py` only. Stop the launcher (Ctrl-C) and restart without the changes if needed.
