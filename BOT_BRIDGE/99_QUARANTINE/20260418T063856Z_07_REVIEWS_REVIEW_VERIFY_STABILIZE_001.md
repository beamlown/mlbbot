# REVIEW_VERIFY_STABILIZE_001

Decision: APPROVED

## What passed

- **Scope**: only `launch_all.py` and `dashboard_server.py` modified — matches allowed_files exactly. `do_not_touch_respected: true` confirmed by worker.
- **launch_all.py**: `resolution_watcher` added as the 4th PROCESSES entry at lines 39-44. Entry matches handoff spec exactly: `name="resolution_watcher"`, `command=[sys.executable, "-m", "integration.resolution_watcher"]`, `cwd=str(MLB_MODEL_DIR)`, `log_file=str(LOG_DIR / "resolution_watcher.log")`.
- **dashboard_server.py**: Date guard added at lines 473-492 inside `_read_mlb_shadow()`. Logic: `today_str = _date.today().isoformat()`, `_slug_is_today_or_newer()` parses slug via `rsplit("-", 3)`, reconstructs `YYYY-MM-DD`, compares to today. Fails open on parse error. Applied as a dict comprehension filter on `recs_by_market` before the display sort/slice. Correctly keyed on `market_slug` from rec dict.
- **Import**: `_date` import already exists at line 17 (`from datetime import date as _date`). No missing import issue.
- **PID guard**: Second launcher attempt confirmed still working: `ERROR: launcher already running at PID 42348. Stop it first.`
- **Rollback**: Both files are independently revertable. Rollback path unchanged.

## What failed / partial

- **Live runtime verification blocked**: The running launcher/dashboard processes predate the code changes, so `/api/mlb-shadow` still returns stale 2026-04-04 recs in the current process. `resolution_watcher` not yet live. This is expected — worker correctly did not take restart authority outside task scope.
- **Verification commands**: `/api/mlb-shadow` stale check was attempted but returned stale results due to pre-change process still running. Cannot be green until restart.

## Notes

- The code changes are correct and complete. The only remaining action is a manager-controlled restart of the launcher stack.
- Worker identified 2 launch_all.py PIDs (30764 + 42348) — consistent with earlier Windows Store Python shim behavior (shim + real process = 2 PIDs for 1 logical process). Not a duplicate launcher issue.
- After restart, the full acceptance criteria can be verified: 4 child processes started, stale recs count = 0.

## Next action

**Manager must restart the launcher stack.** Stop current launcher (kill PIDs or Ctrl-C), then:

```
cd C:\Users\johnny\Desktop\sports_bot_v2
python launch_all.py
```

Expected: 4 LAUNCHER lines (shadow_engine, bot_core, dashboard, resolution_watcher).

Then verify stale recs are gone:
```
python -c "import requests; recs=requests.get('http://localhost:8900/api/mlb-shadow').json().get('recs',[]); stale=[r for r in recs if '2026-04-04' in r.get('market_slug','')]; print('stale recs:', len(stale))"
```

Expected: `stale recs: 0`
