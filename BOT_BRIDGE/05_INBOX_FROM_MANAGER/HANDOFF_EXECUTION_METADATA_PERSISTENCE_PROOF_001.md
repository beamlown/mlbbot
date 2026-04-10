# HANDOFF - EXECUTION_METADATA_PERSISTENCE_PROOF_001
## Prove execution metadata persists into opened-position artifact via isolated DB path

Metadata fields under proof:
- `held_outcome_label`
- `home_team`, `away_team`, `tracked_team`
- `tp_price`, `sl_price`
- `recommended_size_dollars`
- `reasons`
- freshness timestamps/ages
- `game_status`, `inning`, `outs`
- `source`
- `market_slug`, `market_id`

Safe proof method:
- Use a visible helper script
- Point `DB_PATH` to an isolated throwaway SQLite DB under BOT_BRIDGE
- Construct a representative bridge-issued payload
- Run the existing `open_position()` + `insert_open_trade()` path against the isolated DB only
- Read back the persisted trade artifact directly

Why this is safe:
- no live trade is placed
- production DB is not mutated
- production code behavior is only exercised against the isolated DB path
