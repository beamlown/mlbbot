# HANDOFF - MODEL_AUTHORITY_001
## Enforce model authority by disabling local MLB trade origination in production

Allowed files:
- `C:\Users\johnny\Desktop\sports_bot_v2\bot_core.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\core\signal_base.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\core\model_bridge.py`
- `C:\Users\johnny\Desktop\mlb_model\integration\recommendation_api.py`
- BOT_BRIDGE task/result/review files

Current authority violation:
- `sports_bot_v2` still originates MLB trades locally in `bot_core.py`
- local path calls `generate_signal(...)` from `core\signal_base.py`
- that path still creates local `BUY_YES` / `BUY_NO` / no-trade decisions and confidence
- bridge path exists, but production is not forced through it

Exact local decision source verified:
- `bot_core.py` main loop -> `generate_signal(...)` -> local signal -> `check_entry_gates(...)` -> `open_position(...)` -> `insert_open_trade(...)`
- `signal_base.py` constructs local side/confidence/fair-value style signal outputs

Bridge path that should remain after cleanup:
- `mlb_model` recommendation
- `core\model_bridge.py` intake / schema / freshness filtering
- `bot_core.py` bridge branch -> execution checks -> `open_position(...)` -> `insert_open_trade(...)`

Minimum first-step change:
- Add a production-safe gate in `bot_core.py` so local MLB origination is disabled by default
- Leave bridge execution path intact
- Leave execution/risk protections intact
- Do not redesign bridge payload in this step

Current bridge thinning still unresolved after this step:
- bridge currently keeps only a reduced subset like slug, side, entry_px, confidence, edge, source
- fuller model-owned fields like explicit TP/SL/size recommendation/thesis detail are not fully preserved end-to-end yet

Rollback:
- Revert the narrow `bot_core.py` change or set the temporary local-origination flag back on if emergency rollback is needed
