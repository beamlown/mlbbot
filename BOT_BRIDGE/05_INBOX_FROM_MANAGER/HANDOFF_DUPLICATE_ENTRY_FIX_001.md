# HANDOFF — DUPLICATE_ENTRY_FIX_001
## Fix duplicate paper trade entry — DB-level atomic dedup + NULL return handling

---

## ✅ STATUS: ACTIVE — proceed immediately.

---

## What happened (verified from logs)

Two `bot_core.py` processes are running simultaneously. Each has its own bridge loop. Both execute the bridge at nearly the same time with slightly offset loop timers. This is confirmed by paired log entries appearing 1–70ms apart throughout `logs/bot_baseball_20260405.log`:

```
18:25:22,296 — BRIDGE OPEN trade=99  mlb-sea-laa BUY_NO @0.4121   ← Process A
18:25:22,297 — BRIDGE CAP HIT 3/3                                   ← Process A stops
18:25:22,348 — BRIDGE OPEN trade=100 mlb-sea-laa BUY_NO @0.4121   ← Process B (52ms later)
18:25:22,351 — BRIDGE CAP HIT 4/3                                   ← Process B stops
```

Identical slug, identical price, 52ms apart. Both passed every gate. Both committed to the DB. The log has 6 such duplicate pairs today, and 10/3 and 11/3 capacity violations from April 4th.

**The root cause is not in the bridge's dedup logic — that logic is correct but not atomic.** The check `if intent["slug"] in current_open_slugs` runs correctly. The problem is there is no lock between the check and the insert. Two processes both read "slug not open", both decide to write, both succeed because the DB has no constraint preventing it.

**Do NOT touch**: `dashboard.html`, `dashboard_server.py`, `launch_all.py`, `core/paper_exec.py`, `core/risk.py`, `core/model_bridge.py`, `.env`, `mlb_model/`

---

## Fix 1 — DB-level UNIQUE constraint (core/db.py)

Open `core/db.py`. Find `_CREATE_SQL`. After the existing `CREATE INDEX` statements, add:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_one_open_per_slug
ON trades(market_slug) WHERE status='open';
```

This is a **partial unique index** — it only applies to rows where `status='open'`. This means:
- Two open rows for the same slug → **impossible** (DB rejects the second INSERT with IntegrityError)
- Closing a trade changes its status to `'closed'`, which is excluded from the index → re-opening the same slug in a future game is **allowed**
- This is the correct semantic: one active paper position per market at a time

**Migration warning**: If duplicate open rows already exist in the DB, `CREATE UNIQUE INDEX IF NOT EXISTS` will fail silently (or raise an error). Wrap it in a separate try/except in `init_db()`:

```python
try:
    with _db_conn("add_open_slug_unique_idx") as conn:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_one_open_per_slug "
            "ON trades(market_slug) WHERE status='open'"
        )
        conn.commit()
    logger.info("DB: unique open-slug index in place")
except sqlite3.OperationalError as e:
    logger.warning("DB: could not create open-slug unique index (duplicate rows exist?): %s", e)
```

---

## Fix 2 — Atomic check-before-insert using BEGIN IMMEDIATE (core/db.py)

Replace the body of `insert_open_trade()` with an atomic version.

Current function signature: `def insert_open_trade(trade: Trade, sport: str = "unknown") -> int:`

**New signature**: `def insert_open_trade(trade: Trade, sport: str = "unknown") -> int | None:`

New body:

```python
def insert_open_trade(trade: Trade, sport: str = "unknown") -> int | None:
    with _db_conn("insert_open_trade") as conn:
        # BEGIN IMMEDIATE acquires an exclusive write lock immediately.
        # No other SQLite writer can start a transaction until this one commits or rolls back.
        # This makes the check-and-insert atomic even across concurrent processes.
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            "SELECT id FROM trades WHERE market_slug=? AND status='open' LIMIT 1",
            (trade.market_slug,),
        ).fetchone()
        if existing:
            logger.warning(
                "Duplicate open rejected: slug=%s already open (existing id=%s)",
                trade.market_slug, existing[0],
            )
            conn.execute("ROLLBACK")
            return None
        try:
            c = conn.cursor()
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
                    "open", sport, getattr(trade, "source", "bot"),
                ),
            )
            conn.commit()
            row_id = c.lastrowid
            logger.info("Opened trade id=%d %s @ %.4f", row_id, trade.side, trade.entry_px)
            return row_id
        except sqlite3.IntegrityError as e:
            logger.warning(
                "Duplicate insert blocked by unique constraint: slug=%s err=%s",
                trade.market_slug, e,
            )
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            return None
```

**Why BEGIN IMMEDIATE works**: SQLite allows only one writer at a time. `BEGIN IMMEDIATE` acquires the write lock at transaction start, not at first write. So when Process A calls `BEGIN IMMEDIATE`, Process B's attempt to do the same is blocked (waits for `busy_timeout`) until A commits. By the time B gets the lock, A has already committed, and B's SELECT sees the trade as open → B returns None without writing.

---

## Fix 3 — Handle None in native loop (bot_core.py)

In `bot_core.py`, find the native signal loop (around line 425). Currently:

```python
trade = open_position(market, sig, ob, mode=mode_ctx.mode)
trade_id = insert_open_trade(trade, sport=SPORT)
trade.id = trade_id
open_count += 1
open_per_market[market.market_id] = open_per_market.get(market.market_id, 0) + 1
```

Replace with:

```python
trade = open_position(market, sig, ob, mode=mode_ctx.mode)
trade_id = insert_open_trade(trade, sport=SPORT)
if trade_id is None:
    logger.info("OPEN SKIPPED (duplicate slug) slug=%s", market.slug)
    continue
trade.id = trade_id
open_count += 1
open_per_market[market.market_id] = open_per_market.get(market.market_id, 0) + 1
```

---

## Fix 4 — Handle None in bridge section (bot_core.py)

In `bot_core.py`, find the bridge section (around line 484). Currently:

```python
trade = open_position(market, signal, ob, mode=mode_ctx.mode, source="model_bridge")
trade_id = insert_open_trade(trade, sport=SPORT)
trade.id = trade_id
logger.info("BRIDGE OPEN trade=%d %s %s @ %.4f source=%s", trade_id, ...)
```

Replace with:

```python
trade = open_position(market, signal, ob, mode=mode_ctx.mode, source="model_bridge")
trade_id = insert_open_trade(trade, sport=SPORT)
if trade_id is None:
    logger.info("BRIDGE OPEN SKIPPED (duplicate slug) slug=%s", market.slug)
    continue
trade.id = trade_id
logger.info("BRIDGE OPEN trade=%d %s %s @ %.4f source=%s", trade_id, ...)
```

---

## What this guarantees after the fix

- **Process A and Process B both try to open `mlb-sea-laa`**:
  - A gets `BEGIN IMMEDIATE` first → checks → slug not open → inserts → commits → returns `trade_id`
  - B waits for lock → gets it → checks → slug IS now open → logs warning → returns `None`
  - B's caller sees `None` → logs "BRIDGE OPEN SKIPPED" → `continue`
  - Result: exactly 1 trade written

- **Capacity counts**: After this fix, the cap violation (4/3) is also prevented. If B skips the duplicate, it doesn't increment the count. No more 4/3, no more 10/3.

- **Existing duplicate rows**: Not affected by this fix. They remain in the DB. The UNIQUE INDEX will fail to create if duplicates exist; that's OK — the `BEGIN IMMEDIATE` check still works without the index. The duplicates can be manually reviewed and closed/voided separately.

---

## Verification

1. Read `core/db.py` — confirm `BEGIN IMMEDIATE` in `insert_open_trade()`
2. Read `core/db.py` — confirm `IntegrityError` caught and returns `None`
3. Read `core/db.py` — confirm UNIQUE INDEX added in `init_db()` with try/except wrapper
4. Read `bot_core.py` — confirm `if trade_id is None: continue` in native loop
5. Read `bot_core.py` — confirm `if trade_id is None: continue` in bridge section
6. Trace: two calls to `insert_open_trade(slug='mlb-sea-laa-...')` with BEGIN IMMEDIATE → first returns `int`, second returns `None`

---

## Rollback

Revert `core/db.py` and `bot_core.py`. If the UNIQUE INDEX was successfully created in the DB file, it can be dropped manually: `DROP INDEX IF EXISTS idx_trades_one_open_per_slug` — but this is not required for rollback; the index is safe to keep.
