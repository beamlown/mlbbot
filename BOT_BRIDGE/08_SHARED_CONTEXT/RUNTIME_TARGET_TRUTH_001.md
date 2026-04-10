# RUNTIME_TARGET_TRUTH_001

## Correct runtime server target
- Host bind: `0.0.0.0`
- Local verification URL: `http://localhost:8900`
- Effective local loopback target: `http://127.0.0.1:8900` should also work when the server is running

## Source of truth
From `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`:
- file header states: `Port: 8900 (set via DASHBOARD_PORT env var)`
- config sets: `PORT = int(os.getenv("DASHBOARD_PORT", "8900"))`
- server starts on: `ThreadingHTTPServer(("0.0.0.0", PORT), DashHandler)`
- local launch URL is: `http://localhost:{PORT}`

## Correct verification endpoints
Use this base URL:
- `http://localhost:8900`

Expected verification endpoints:
- `http://localhost:8900/api/state`
- `http://localhost:8900/api/games`
- `http://localhost:8900/api/trades?limit=60`
- `http://localhost:8900/api/stream/state`

## Dashboard evidence
`dashboard.html` fetches relative endpoints:
- `/api/state`
- `/api/games`
- `/api/trades?limit=60`
- `/api/stream/state`

That means verification must target whatever host/port is actually serving `dashboard.html`. For this system, the server definition points to port `8900`, not `8000`.

## Recent tasks that used the wrong target
- `LIVE_SESSION_VERIFY_001`

## Wrong runtime target used
- `http://127.0.0.1:8000`

## Conclusion
The recent verification failure was caused by using the wrong port assumption. The proven current runtime target is the dashboard server on port `8900`, unless overridden by `DASHBOARD_PORT` in the live environment.
