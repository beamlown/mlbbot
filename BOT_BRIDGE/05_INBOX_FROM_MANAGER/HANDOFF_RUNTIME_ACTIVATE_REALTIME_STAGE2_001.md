# HANDOFF - RUNTIME_ACTIVATE_REALTIME_STAGE2_001
## Activate live Stage 2 SSE runtime and verify route emission

Live process believed to serve localhost:8900:
- standalone `python.exe` running `dashboard_server.py`
- verified via the listener on port 8900

Safest reload/restart path:
- restart only the dashboard server process bound to port 8900
- do not restart the full launcher tree unless necessary
- do not change code unless a hard failure is proven

Verification after activation:
- confirm `GET /api/stream/state` returns 200
- capture at least one live SSE `positions_mark` event payload
- confirm `/api/state` and `/api/trades` still return 200
