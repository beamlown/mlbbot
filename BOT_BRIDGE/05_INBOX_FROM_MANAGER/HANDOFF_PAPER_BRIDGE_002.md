# Worker Handoff Note — PAPER_BRIDGE_002
## Created: 2026-04-04

---

## PAPER MODE ONLY

No real money. No live order placement. No exchange connection. This writes to a local SQLite paper trade database only.

---

## Why this exists

PAPER_BRIDGE_001 was BLOCKED because `source="model_bridge"` cannot be persisted without touching `paper_exec.py` and `db.py`. Those were listed as do_not_touch in the original brief. This task expands scope exactly as far as the persistence path requires — no further.

---

## Task brief location

`C:\Users\johnny\Desktop\BOT_BRIDGE\05_INBOX_FROM_MANAGER\TASK_PAPER_BRIDGE_002.json`

---

## Files you may touch

```
core/types.py           ← add source field to Trade dataclass
core/db.py              ← add source column, migration, update INSERT/SELECT
core/paper_exec.py      ← add source param to open_position()
dashboard_server.py     ← read source from DB column instead of hard-coding 'bot'
core/model_bridge.py    ← new file — gate logic + bridge call (from PAPER_BRIDGE_001)
bot_core.py             ← minimal additive bridge call (from PAPER_BRIDGE_001)
```

Do not touch: `risk.py`, `signal_base.py`, `dashboard.html`, anything in `mlb_model/`.

---

## Read these before writing anything

```
C:\Users\johnny\Desktop\sports_bot_v2\core\types.py
```
Find the `Trade` dataclass (around line 114). It currently has no `source` field.

```
C:\Users\johnny\Desktop\sports_bot_v2\core\db.py
```
Find `_CREATE_SQL` — `trades` table has no `source` column. Find `insert_open_trade()` — source is not in the INSERT. Find `_row_to_trade()` and `fetch_open_trades()` / `fetch_recent_closed()` — source is not selected.

```
C:\Users\johnny\Desktop\sports_bot_v2\core\paper_exec.py
```
Find `open_position()` — no `source` parameter. It constructs and returns a `Trade`.

```
C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py
```
Find `_fetch_trades()` around line 233. It currently hard-codes `"source": "bot"` for all DB rows.

---

## What to build — in this exact order

### 1. `core/types.py` — add source to Trade

```python
@dataclass
class Trade:
    ...
    status: str               # "open" | "closed"
    source: str = "bot"       # ← add this line
```

Default `"bot"` means every existing Trade construction site continues to work with zero changes.

---

### 2. `core/db.py` — three changes

**a) Schema migration** — add to `init_db()` (or a `_migrate_db()` called from `init_db()`):

```python
# Additive migration — safe to run on existing databases
try:
    with _db_conn("migrate_source_col") as conn:
        conn.execute("ALTER TABLE trades ADD COLUMN source TEXT DEFAULT 'bot'")
        conn.commit()
    logger.info("DB migration: added source column")
except sqlite3.OperationalError:
    pass  # column already exists — normal after first run
```

Do NOT add `source` to `_CREATE_SQL`. The `CREATE TABLE IF NOT EXISTS` won't run on existing databases, so the migration is the correct path for existing installs.

**b) `insert_open_trade()`** — add source to INSERT:

```python
c.execute(
    """INSERT INTO trades
       (ts_open, ts_close, market_slug, market_id, side, qty, entry_px,
        exit_px, pnl_usd, fees_usd, reason_open, reason_close,
        confidence, mode, status, sport, source)
       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (
        trade.ts_open, trade.ts_close,
        trade.market_slug, trade.market_id,
        trade.side, trade.qty, trade.entry_px,
        trade.exit_px, trade.pnl_usd, trade.fees_usd,
        trade.reason_open, trade.reason_close,
        trade.confidence, trade.mode,
        "open", sport,
        getattr(trade, "source", "bot"),   # backward-safe
    ),
)
```

**c) `fetch_open_trades()`, `fetch_recent_closed()`, and `_row_to_trade()`** — add `source` to SELECT and row mapping. Check how `_row_to_trade()` maps columns and add source there too.

---

### 3. `core/paper_exec.py` — add source param

```python
def open_position(
    market: Market,
    signal: Signal,
    ob: OBSnapshot,
    mode: str = "neutral",
    source: str = "bot",        # ← add this parameter
) -> Trade:
    ...
    return Trade(
        ...
        source=source,           # ← pass through
    )
```

All existing callers of `open_position()` pass no `source` argument — they will continue to get `source="bot"` by default. No other callers need to change.

---

### 4. `dashboard_server.py` — read source from DB

In `_fetch_trades()` around line 237, change:

```python
# BEFORE:
"SELECT id,ts_open,ts_close,market_slug,side,entry_px,exit_px,"
"pnl_usd,reason_open,reason_close,confidence,mode,status,qty "

# AFTER:
"SELECT id,ts_open,ts_close,market_slug,side,entry_px,exit_px,"
"pnl_usd,reason_open,reason_close,confidence,mode,status,qty,source "
```

And in the result dict, replace the hard-coded `"source": "bot"` with:

```python
"source": r["source"] or "bot",   # read from column, fallback for NULLs
```

Existing rows have column default `"bot"` — no regression. Model-bridge rows will show `"model_bridge"`.

---

### 5. `core/model_bridge.py` — new file

Implement all gates from PAPER_BRIDGE_001. Key constants at top:

```python
ENABLE_MODEL_BRIDGE = False   # ← must stay False in submitted patch

APPROVED_MODEL_VERSIONS = {"mlb_winprob_v1_lgbm"}
MAX_REC_AGE_SECONDS = 120
MIN_EDGE = 0.05
MIN_CONFIDENCE = 0.25
MAX_GAME_STATE_AGE = 60
MAX_BOOK_AGE = 30
SHADOW_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "mlb_model", "logs", "shadow_recommendations.jsonl")
SOURCE_LABEL = "model_bridge"
```

**Step 0 — Kill switch:**
```python
if not ENABLE_MODEL_BRIDGE:
    logger.info("BRIDGE DISABLED — set ENABLE_MODEL_BRIDGE=True to activate")
    return []
```

**Step 1 — Deduplicate log before any gate:**
1. Read shadow log (last N lines for efficiency — suggest 500)
2. Discard entries where `action == "NO_TRADE"`
3. Keep only **latest entry per `market_slug`** by `feature_timestamp` or `ts`

**Step 2 — Gate each entry (stop at first failure, log rejection):**
1. `model_version` in `APPROVED_MODEL_VERSIONS`
2. `action` is `BUY_YES` or `BUY_NO`
3. `now - feature_timestamp < MAX_REC_AGE_SECONDS`
4. Slug contains no `nrfi`, `spread`, `total`, `o/u`, `prop`
5. Date in slug == `date.today()`
6. Edge: `edge_yes >= MIN_EDGE` (BUY_YES) or `edge_no >= MIN_EDGE` (BUY_NO)
7. `confidence >= MIN_CONFIDENCE`
8. `game_state_age_sec < MAX_GAME_STATE_AGE`
9. `book_age_sec < MAX_BOOK_AGE`
10. Slug not in `open_slugs`
11. One intent per slug per batch

Log: `BRIDGE GATE REJECT [gate_name] slug=... reason=...`
Log: `BRIDGE GATE PASS slug=... side=... edge=... confidence=...`

**Return value:** list of dicts with `slug`, `side`, `entry_px`, `source="model_bridge"`, `confidence`, `market_id`

---

### 6. `bot_core.py` — minimal addition

After the existing main loop body, add the bridge call. Find the right insertion point by reading bot_core.py first. Pass `source="model_bridge"` when calling `paper_exec.open_position()`. Do not replace existing logic — additive only.

---

## Kill switch reminder

`ENABLE_MODEL_BRIDGE = False` must remain `False` in the submitted patch. To test gate logic, flip it temporarily, observe BRIDGE GATE PASS / BRIDGE GATE REJECT log entries, then flip it back to `False` before writing your result file.

---

## How to verify

```
cd C:\Users\johnny\Desktop\sports_bot_v2
python bot_core.py
```

Confirm:
- `BRIDGE DISABLED — set ENABLE_MODEL_BRIDGE=True to activate` in logs
- Existing open positions still appear in `runtime/state.json`
- DB migration ran without error (`DB migration: added source column` or no error on second run)

```
python dashboard_server.py
```

Hit `/api/trades` — existing trades should show `source='bot'`. No regressions.

For gate testing: flip `ENABLE_MODEL_BRIDGE=True`, rerun, look for `BRIDGE GATE PASS` or `BRIDGE GATE REJECT`. If a position is created, check `state.json` for `source=model_bridge`. Flip back to `False` before submitting.

---

## How to deliver

```
C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_PAPER_BRIDGE_002.json
```

Include:
- `files_changed`: exact list
- `summary`: describe source persistence path built
- `schema_changes`: describe the migration and column added
- `gates_implemented`: list all gates and thresholds
- `commands_run`
- `tests_run`: what gate passes/rejections you observed, what existing trade behavior you confirmed
- `result`
- `risks`
- `next_recommended_task`

---

## Rollback

Revert `core/types.py`, `core/db.py`, `core/paper_exec.py`, `dashboard_server.py`, `bot_core.py`. Delete `core/model_bridge.py`. The `source` column will remain in the SQLite DB but is harmless — data is unaffected and the column has a safe default.
