# HANDOFF - MARKET_STREAM_DEBUG_STATUS_FIX_001
## Stabilize /api/debug/market-stream for safe runtime chain diagnostics

Exact endpoint failure:
- `GET /api/debug/market-stream` was closing the connection unexpectedly instead of returning JSON.

Most likely cause that was checked first:
- the debug status path itself was broken, preventing safe runtime introspection.

Exact minimal fix made:
- fixed `debug_status()` placement in `core/market_stream.py` so it is a real method on `MarketStreamClient`
- left the endpoint read-only and JSON-safe
- no strategy/execution behavior changes

Rollback:
- revert the narrow `debug_status()` method placement/handler stabilization changes
