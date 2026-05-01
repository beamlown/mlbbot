# HANDOFF - DISCOVERY_TOKEN_IDS_001
## Persist token IDs into discovery cache for realtime market-stream mapping

Allowed files:
- `C:\Users\johnny\Desktop\sports_bot_v2\core\discovery.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\core\types.py` only if strictly necessary
- BOT_BRIDGE task/result/review files

Where token IDs are currently parsed:
- `core/discovery.py` `_parse_market(...)`
- token IDs are placed onto the existing `Market` dataclass fields:
  - `yes_token_id`
  - `no_token_id`

Where token IDs were being lost:
- in the reduced serializer block that writes `runtime/last_discovery.json`
- the cache writer persisted only a subset of market fields and omitted token IDs

Types check:
- `core/types.py` already supports `yes_token_id` / `no_token_id`
- no type change required

Rollback:
- revert the narrow cache serializer change in `core/discovery.py`
