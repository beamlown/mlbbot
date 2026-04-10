# REVIEW_LAUNCH_002

Decision: APPROVED

## What passed
- Scope: only `launch_all.py` changed — matches allowed_files exactly.
- All three managed processes confirmed started on first launch: shadow_engine, bot_core, dashboard.
- PID guard confirmed working: second launch attempt printed ERROR: launcher already running.
- Both verification commands from the task brief were run.
- Rollback path intact.

## What failed
- none

## Notes
- dashboard_server.py is now fully under the launcher's watchdog. Manual `python dashboard_server.py` calls are no longer needed and will now cause duplicate instances if the launcher is already running — do not do this.
- Fresh slate is in place (DB cleared, state.json deleted). Ready to restart.

## Next action
- Manager restarts bot via `python launch_all.py`. Done.
