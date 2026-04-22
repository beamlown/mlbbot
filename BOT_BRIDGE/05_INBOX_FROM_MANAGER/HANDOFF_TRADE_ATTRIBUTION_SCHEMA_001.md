<!-- writer: manager, task_id: TRADE_ATTRIBUTION_SCHEMA_001, patch_id: pending, written_at: 2026-04-18T17:35:49Z, attempt: 1 -->

# HANDOFF: TRADE_ATTRIBUTION_SCHEMA_001

## Status
QUEUED — P0 phase, Attribution Spine. This is the foundation task; nothing downstream works without it.

## What you are doing
Extend the trades database schema and add a per-trade forensics JSONL writer so
every paper trade produces a complete audit record we can use for calibration,
edge-realization, and trade-class analysis.

## Why this exists
The bot is in paper mode to validate edge before going live. We cannot answer
"does the model have edge?" without attribution data on every trade. Once this
schema exists, downstream tasks (wiring, dashboard, replay harness) hang off it.

## Target files
- `C:\Users\johnny\Desktop\sports_bot_v2\core\db.py` — schema migration
- `C:\Users\johnny\Desktop\sports_bot_v2\core\attribution.py` — NEW file: JSONL writer + dataclass
- `C:\Users\johnny\Desktop\sports_bot_v2\runtime\trade_attribution.jsonl` — created on first write

## Schema to add

Add the following columns to the `trades` table (use `ALTER TABLE ... ADD COLUMN` — do NOT recreate the table):

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `entry_model_prob` | REAL | yes | Model's win prob at fill moment |
| `entry_market_prob` | REAL | yes | Market-implied prob at fill moment |
| `expected_edge_pct` | REAL | yes | `entry_model_prob - entry_market_prob` |
| `actual_fill_px` | REAL | yes | Simulated paper fill price |
| `actual_fill_size` | REAL | yes | Size filled |
| `exit_reason` | TEXT | yes | enum: `TP`, `SL`, `RESOLUTION`, `MANUAL`, `SESSION_CAP`, `COOLDOWN` |
| `exit_model_prob` | REAL | yes | Model prob at exit |
| `exit_market_prob` | REAL | yes | Market-implied prob at exit |
| `hold_seconds` | INTEGER | yes | `(exit_ts - entry_ts)` in seconds |
| `resolved_winner` | TEXT | yes | Side that won the underlying market |
| `model_side_was_right` | INTEGER | yes | 0/1 — did model's favored side win |
| `trade_class` | TEXT | yes | enum (see below) |
| `attribution_version` | INTEGER | yes | Integer version of the attribution logic — start at 1 |

Add an index on `trade_class` and one on `exit_reason`.

`trade_class` enum values:
- `MODEL_WIN_EXPECTED` — model was right, expected_edge_pct > 0 at entry
- `MODEL_WIN_LUCKY` — model was right but expected_edge_pct ≤ 0 at entry
- `MODEL_LOSS_EXPECTED` — model was wrong, expected_edge_pct ≤ 0 at entry (shouldn't have traded)
- `MODEL_LOSS_EXECUTION` — model was right directionally but we lost P&L (stop, slippage, cap)
- `UNRESOLVED` — trade closed without market resolution (e.g. MANUAL exit before game ended)

## attribution.py file structure

```python
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Literal

ExitReason = Literal["TP", "SL", "RESOLUTION", "MANUAL", "SESSION_CAP", "COOLDOWN"]
TradeClass = Literal[
    "MODEL_WIN_EXPECTED", "MODEL_WIN_LUCKY",
    "MODEL_LOSS_EXPECTED", "MODEL_LOSS_EXECUTION",
    "UNRESOLVED",
]

ATTRIBUTION_VERSION = 1

@dataclass
class TradeAttribution:
    trade_id: str
    entry_model_prob: float | None
    entry_market_prob: float | None
    expected_edge_pct: float | None
    actual_fill_px: float | None
    actual_fill_size: float | None
    exit_reason: ExitReason | None
    exit_model_prob: float | None
    exit_market_prob: float | None
    hold_seconds: int | None
    resolved_winner: str | None
    model_side_was_right: bool | None
    realized_pnl: float | None
    trade_class: TradeClass | None
    attribution_version: int = ATTRIBUTION_VERSION

def classify_trade(
    *, model_side_was_right: bool | None,
    expected_edge_pct: float | None,
    exit_reason: ExitReason | None,
    realized_pnl: float | None,
) -> TradeClass:
    # ... implement per enum rules above
    ...

def write_jsonl(record: TradeAttribution, path: Path) -> None:
    # append-only, one JSON per line, with ISO-8601 UTC timestamp wrapper
    ...
```

## Migration safety
- The migration must be idempotent: check `PRAGMA table_info(trades)` and only
  add columns that don't exist.
- Add a migration marker: row in `meta` table (create if absent) keyed
  `attribution_schema_version = 1`.
- No data loss. If the DB has existing trades, they get NULL for the new columns
  (TRADE_ATTRIBUTION_WIRING_001 will backfill later).

## Output / deliverables
1. Modified `core/db.py` with idempotent migration run at startup
2. New file `core/attribution.py` with dataclass + classifier + writer
3. Result JSON at `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_TRADE_ATTRIBUTION_SCHEMA_001.json`

## Result JSON fields required
```json
{
  "task_id": "TRADE_ATTRIBUTION_SCHEMA_001",
  "status": "ok",
  "db_columns_added": ["..."],
  "indexes_added": ["..."],
  "attribution_module_path": "...",
  "migration_idempotency_proof": "ran migration twice, second run no-op",
  "files_changed": ["..."]
}
```

## Do NOT do
- No wiring changes in `bot_core.py` or `core/paper_exec.py` (that is TRADE_ATTRIBUTION_WIRING_001)
- No dashboard changes (that is ATTRIBUTION_DASHBOARD_001)
- No changes to the model or recommendation code
- No schema change that drops or renames existing columns
- No bankroll/sizing changes
