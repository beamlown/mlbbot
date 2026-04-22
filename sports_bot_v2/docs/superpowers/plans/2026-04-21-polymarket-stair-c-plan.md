# Polymarket Stair C (C1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full signed-order placement path (`place_order`, `cancel_order`, `cancel_all`) as dead code behind two independent kill-switches. Paper trading continues unchanged. A future operator flips `PHASE=live` + `LIVE_TRADING_KILL_SWITCH=false` + `SIGNER=private_key` + a funded Polygon wallet to place real orders — zero additional code work required at that moment.

**Architecture:** Three new modules in `core/`. `signer.py` owns the `Signer` protocol and two implementations (`DummySigner` for test/build-time, `PrivateKeySigner` for the future). `live_exec.py` wraps tick-snapping + dual-gate kill-switches + the py_clob_client `post_order` call path. `paper_exec.open_position` branches on `PHASE`: the default `paper` branch keeps current local book-walk behavior; the `live` branch calls `live_exec.place_order` and inserts `status='pending'` rows until Stair B's user_stream delivers the fill event. Nothing in this cycle ever exercises the `live` branch — **no real capital is at risk during this work.**

**Tech Stack:** Python 3.14, `py_clob_client 0.34.6` (already installed), `eth_account`/`eth-keys` (already installed for future Stair C production wiring), `pytest 9.0.2`, `unittest.mock`.

**Spec reference:** `docs/superpowers/specs/2026-04-20-polymarket-integration-design.md` (Stair C section)

**Work-order alias:** `STAIR_C_LIVE_EXEC_BUILD_001`

**Prereqs assumed satisfied:**
- Stair A landed (commits `40f6e2e` → `6575151`). `core/polymarket_client.py` exists with `tick_size()`, `batch_midpoints()`, etc. Tests pass.
- Live bot is running on PID 9056 with `USE_BATCH_PRICES=true`. **Do not kill or restart it during this work.** The bot respawns via launcher; changes take effect at whatever next restart happens organically.

---

## File Structure

| File | Role | New/Modify |
|---|---|---|
| `core/polymarket_client.py` | Lock + atomic write on `_save_tick_cache` (preflight for hot-path races) | MODIFY (lines ~48-71) |
| `core/signer.py` | `Signer` protocol, `DummySigner`, `PrivateKeySigner`, `get_signer()` factory | **NEW** |
| `core/live_exec.py` | `place_order`, `cancel_order`, `cancel_all` with dual-gate kill-switches | **NEW** |
| `core/paper_exec.py` | Branch `open_position` on `PHASE`; live path calls `live_exec.place_order` | MODIFY (lines ~198-292) |
| `core/db.py` | Add `order_id TEXT` column migration + include in insert/select queries | MODIFY |
| `core/types.py` | Add `order_id: str \| None = None` field to `Trade` dataclass | MODIFY |
| `bot_core.py` | Handle `Trade | None` return from `open_position` (live-reject case) | MODIFY (line ~780 region) |
| `tests/core/test_signer.py` | DummySigner structure, PrivateKeySigner fail-loud, factory | **NEW** |
| `tests/core/test_live_exec.py` | Dual-gate matrix, tick-snap, cancel paths, all exercised via DummySigner | **NEW** |
| `tests/core/test_paper_exec_phase_branch.py` | paper mode unchanged + live mode routes through live_exec | **NEW** |
| `.env.example` | Document `PHASE`, `LIVE_TRADING_KILL_SWITCH`, `SIGNER` with safety warnings | MODIFY |

---

## Task 1: Preflight — thread-safe atomic tick-cache write (closes tracked task #26)

**Why now:** Stair C's `live_exec.place_order` will call `polymarket_client.tick_size()` on the hot path. Multiple concurrent calls from a future multi-threaded live-execution path could race on `_save_tick_cache`: two threads both `json.dumps` the cache to a tempbuf, then both `write_text` in partial-overwrite order → last-write-wins, possibly losing entries. Fix by serializing saves behind a lock and writing through a temp file atomically renamed with `Path.replace()`.

**Files:**
- Modify: `core/polymarket_client.py` (`_save_tick_cache` function, plus module-level lock)
- Modify: `tests/core/test_polymarket_client.py` (add one test)

- [ ] **Step 1: Append failing test**

Append to `tests/core/test_polymarket_client.py`:

```python
def test_save_tick_cache_writes_atomically(tmp_path, monkeypatch):
    """Concurrent _save_tick_cache calls must serialize; the final file must
    contain the full union of tokens written. Proves the lock + atomic replace
    prevent partial-state corruption."""
    import core.polymarket_client as pm
    import threading

    cache_path = tmp_path / "ticks.json"
    monkeypatch.setattr(pm, "TICK_SIZE_CACHE_PATH", cache_path)
    pm._tick_cache = {}
    pm._tick_cache_loaded = True  # skip disk load

    def writer(tid_prefix: str, count: int):
        for i in range(count):
            pm._tick_cache[f"{tid_prefix}_{i}"] = 0.01
            pm._save_tick_cache()

    threads = [
        threading.Thread(target=writer, args=("A", 20)),
        threading.Thread(target=writer, args=("B", 20)),
        threading.Thread(target=writer, args=("C", 20)),
    ]
    for t in threads: t.start()
    for t in threads: t.join()

    # All 60 tokens must be present in the final file — no partial overwrites
    on_disk = json.loads(cache_path.read_text(encoding="utf-8"))
    assert len(on_disk) == 60, f"expected 60 tokens, got {len(on_disk)}"
    assert all(on_disk[f"A_{i}"] == 0.01 for i in range(20))
    assert all(on_disk[f"B_{i}"] == 0.01 for i in range(20))
    assert all(on_disk[f"C_{i}"] == 0.01 for i in range(20))


def test_save_tick_cache_uses_atomic_replace(tmp_path, monkeypatch):
    """A crash mid-write must not leave a partial file. Verify by checking
    the tempfile pattern: if save fails after temp write but before replace,
    the real file must be untouched."""
    import core.polymarket_client as pm
    cache_path = tmp_path / "ticks.json"
    cache_path.write_text('{"pre_existing": 0.001}', encoding="utf-8")
    monkeypatch.setattr(pm, "TICK_SIZE_CACHE_PATH", cache_path)
    pm._tick_cache = {"new_token": 0.01}
    pm._tick_cache_loaded = True

    # Simulate replace() failing mid-save
    real_replace = pm.Path.replace
    def failing_replace(self, target):
        raise OSError("simulated rename failure")
    monkeypatch.setattr(pm.Path, "replace", failing_replace)

    pm._save_tick_cache()  # should swallow (already does)

    # Original file must be unchanged
    on_disk = json.loads(cache_path.read_text(encoding="utf-8"))
    assert on_disk == {"pre_existing": 0.001}, f"original corrupted: {on_disk}"
    # Restore for other tests
    monkeypatch.setattr(pm.Path, "replace", real_replace)
```

- [ ] **Step 2: Run — verify failure**

Run: `cd "C:/Users/johnny/Desktop/sports_bot_v2" && "C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_polymarket_client.py -v -k "atomic" 2>&1 | tail -20`

Expected: `test_save_tick_cache_writes_atomically` likely passes if concurrent writes happen to not collide (flaky); `test_save_tick_cache_uses_atomic_replace` FAILS because current `_save_tick_cache` writes directly to the target path, so a failed rename is impossible to simulate (the current function has no rename step). Re-running may show different race patterns; that's expected — the point is the CURRENT code can't prove atomicity.

- [ ] **Step 3: Modify `_save_tick_cache` + add module-level lock**

In `core/polymarket_client.py`, near the other module-level state (around line ~37), add:

```python
import threading
_tick_cache_lock = threading.Lock()
```

Replace the existing `_save_tick_cache` function (around lines 64-71) with:

```python
def _save_tick_cache() -> None:
    """Atomically persist _tick_cache to disk. Serialized via _tick_cache_lock
    to prevent concurrent-write corruption. Uses write-to-temp + Path.replace()
    so a crash mid-write leaves the existing file intact.
    """
    with _tick_cache_lock:
        try:
            TICK_SIZE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = TICK_SIZE_CACHE_PATH.with_suffix(TICK_SIZE_CACHE_PATH.suffix + ".tmp")
            tmp_path.write_text(
                json.dumps(_tick_cache, indent=2),
                encoding="utf-8",
            )
            tmp_path.replace(TICK_SIZE_CACHE_PATH)
        except Exception as exc:
            logger.warning("tick_size cache save failed path=%s err=%s", TICK_SIZE_CACHE_PATH, exc)
```

- [ ] **Step 4: Run — verify pass**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_polymarket_client.py -v 2>&1 | tail -25`

Expected: all 17 tests pass (prior 15 + 2 new). If the concurrent test flakes, run it 3× — all runs should pass now that the lock serializes writes.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/polymarket_client.py sports_bot_v2/tests/core/test_polymarket_client.py
git commit -m "sports_bot_v2: atomic + thread-safe tick-size cache writes

_save_tick_cache now serializes through a module-level threading.Lock and
writes to a temp file that Path.replace() atomically renames. Prevents the
hot-path race that would arise once Stair C's live_exec starts calling
tick_size() concurrently from order-placement code.

Closes preflight item tracked as task #26. STAIR_C_LIVE_EXEC_BUILD_001 prep.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: DB migration — add `order_id` column to `trades` table

**Why:** Live-mode trades need a durable link from sqlite row to Polymarket order ID so Stair B's user_stream can update fill price on TRADE events. Paper-mode rows will have `order_id=NULL`.

**Files:**
- Modify: `core/db.py`
- Test: `tests/core/test_db_migration.py` (new)

- [ ] **Step 1: Create the failing test**

Create `tests/core/test_db_migration.py`:

```python
"""Test that db.init_db() adds order_id column idempotently."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


def test_init_db_adds_order_id_column(tmp_path, monkeypatch):
    """Running init_db() against an old-schema trades table must ADD order_id
    without dropping data."""
    # Arrange: make an old-schema trades table with one row
    db_path = tmp_path / "t.db"
    con = sqlite3.connect(db_path)
    con.execute("""
        CREATE TABLE trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_open TEXT,
            market_slug TEXT,
            side TEXT,
            entry_px REAL,
            status TEXT
        )
    """)
    con.execute("INSERT INTO trades (ts_open, market_slug, side, entry_px, status) VALUES (?, ?, ?, ?, ?)",
                ("2026-04-21T00:00:00", "mlb-test-2026-04-21", "BUY_YES", 0.55, "open"))
    con.commit()
    con.close()

    # Act: run init_db pointed at this file
    monkeypatch.setenv("DB_PATH", str(db_path))
    import importlib, core.db
    importlib.reload(core.db)
    core.db.init_db()

    # Assert: order_id column exists; old row survived with order_id=NULL
    con = sqlite3.connect(db_path)
    cols = [r[1] for r in con.execute("PRAGMA table_info(trades)").fetchall()]
    assert "order_id" in cols
    row = con.execute("SELECT market_slug, order_id FROM trades WHERE side='BUY_YES'").fetchone()
    assert row == ("mlb-test-2026-04-21", None)
    con.close()


def test_init_db_is_idempotent(tmp_path, monkeypatch):
    """Running init_db() twice must not error or duplicate columns."""
    db_path = tmp_path / "t2.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    import importlib, core.db
    importlib.reload(core.db)
    core.db.init_db()
    core.db.init_db()  # second call must be a no-op
    con = sqlite3.connect(db_path)
    cols = [r[1] for r in con.execute("PRAGMA table_info(trades)").fetchall()]
    assert cols.count("order_id") == 1
    con.close()
```

- [ ] **Step 2: Run — verify failure**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_db_migration.py -v 2>&1 | tail -20`

Expected: `test_init_db_adds_order_id_column` FAILS (column doesn't exist yet). `test_init_db_is_idempotent` passes trivially if init_db already does nothing on duplicate — the real value is after the migration is added.

- [ ] **Step 3: Read `core/db.py` to find `init_db`**

Run: `grep -n "^def init_db\|CREATE TABLE\|ALTER TABLE" "C:/Users/johnny/Desktop/sports_bot_v2/core/db.py"`

Note the existing `init_db` structure. The `trades` table creation uses `CREATE TABLE IF NOT EXISTS trades (...)` with a column list. Adding a column to an existing DB requires a separate ALTER TABLE because CREATE TABLE IF NOT EXISTS won't modify an existing schema.

- [ ] **Step 4: Add migration helper + call it from init_db**

In `core/db.py`, add a new private helper near `init_db` (match surrounding style):

```python
def _migrate_add_order_id_column(con: sqlite3.Connection) -> None:
    """Idempotent: add `order_id TEXT` column to trades if not already present."""
    cols = [r[1] for r in con.execute("PRAGMA table_info(trades)").fetchall()]
    if "order_id" not in cols:
        con.execute("ALTER TABLE trades ADD COLUMN order_id TEXT")
        con.commit()
```

Inside `init_db`, after the existing `CREATE TABLE IF NOT EXISTS trades (...)` statement (but before the function returns), add a call:

```python
    _migrate_add_order_id_column(con)
```

Also update the `CREATE TABLE IF NOT EXISTS trades (...)` column list to include `order_id TEXT` so fresh DBs have it from the start. Insert alphabetically or at the end of the column list — pick a consistent spot.

- [ ] **Step 5: Run — verify pass**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_db_migration.py -v 2>&1 | tail -15`
Expected: both tests pass.

- [ ] **Step 6: Verify production DB gets migrated on next init_db**

The live bot's `trades_sports.db` does NOT currently have an `order_id` column. When bot_core next restarts, `init_db()` will run and add it. Confirm this works end-to-end:

```bash
cp "C:/Users/johnny/Desktop/sports_bot_v2/trades_sports.db" "C:/Users/johnny/Desktop/sports_bot_v2/trades_sports.db.premigration"
"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -c "
import os
os.environ['DB_PATH'] = 'C:/Users/johnny/Desktop/sports_bot_v2/trades_sports.db'
from core.db import init_db
init_db()
import sqlite3
con = sqlite3.connect('C:/Users/johnny/Desktop/sports_bot_v2/trades_sports.db')
cols = [r[1] for r in con.execute('PRAGMA table_info(trades)').fetchall()]
print('order_id present:', 'order_id' in cols)
print('row count:', con.execute('SELECT COUNT(*) FROM trades').fetchone()[0])
"
```
Expected: `order_id present: True` and non-zero row count (existing trades preserved).

- [ ] **Step 7: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/db.py sports_bot_v2/tests/core/test_db_migration.py
git commit -m "sports_bot_v2: trades.order_id column migration

Idempotent migration in init_db() adds the order_id TEXT column to the
trades table if not already present. Fresh DBs get it via CREATE TABLE;
existing DBs (production trades_sports.db) get an ALTER TABLE. Needed for
Stair C live_exec to link sqlite rows to Polymarket order IDs.

STAIR_C_LIVE_EXEC_BUILD_001 step 1 of N.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Extend `Trade` dataclass + db insert/select with `order_id`

**Files:**
- Modify: `core/types.py` — add `order_id: str | None = None` to `Trade`
- Modify: `core/db.py` — include `order_id` in `insert_open_trade` + `fetch_open_trades` SQL

- [ ] **Step 1: Append failing tests to existing db-migration test file**

Append to `tests/core/test_db_migration.py`:

```python
def test_insert_trade_persists_order_id(tmp_path, monkeypatch):
    """Trade with order_id set must round-trip through insert + fetch."""
    db_path = tmp_path / "t3.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    import importlib, core.db, core.types
    importlib.reload(core.db)
    importlib.reload(core.types)
    core.db.init_db()

    trade = core.types.Trade(
        id=None,
        ts_open="2026-04-21T00:00:00+00:00",
        ts_close=None,
        market_slug="mlb-test-2026-04-21",
        market_id="0xtest",
        side="BUY_YES",
        qty=100.0,
        entry_px=0.55,
        exit_px=None,
        pnl_usd=None,
        fees_usd=0.0,
        reason_open="",
        reason_close=None,
        confidence=0.5,
        mode="neutral",
        status="pending",
        source="live",
        actual_fill_px=0.0,
        order_id="0xpoly_order_abc123",
    )
    core.db.insert_open_trade(trade)

    open_trades = core.db.fetch_open_trades()
    assert len(open_trades) == 1
    assert open_trades[0].order_id == "0xpoly_order_abc123"


def test_insert_trade_with_no_order_id_defaults_to_none(tmp_path, monkeypatch):
    """Paper trades have order_id=None. Must persist as NULL and fetch back as None."""
    db_path = tmp_path / "t4.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    import importlib, core.db, core.types
    importlib.reload(core.db)
    importlib.reload(core.types)
    core.db.init_db()

    trade = core.types.Trade(
        id=None, ts_open="2026-04-21T00:00:00+00:00", ts_close=None,
        market_slug="mlb-paper-2026-04-21", market_id="0xpaper",
        side="BUY_NO", qty=50.0, entry_px=0.45, exit_px=None,
        pnl_usd=None, fees_usd=0.0, reason_open="", reason_close=None,
        confidence=0.4, mode="neutral", status="open", source="bot",
        actual_fill_px=0.0,
        # order_id defaults to None
    )
    core.db.insert_open_trade(trade)
    open_trades = core.db.fetch_open_trades()
    assert len(open_trades) == 1
    assert open_trades[0].order_id is None
```

- [ ] **Step 2: Run — verify fail**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_db_migration.py -v -k "order_id" 2>&1 | tail -20`

Expected: both new tests FAIL — `Trade.__init__` rejects `order_id` kwarg (or fetch returns rows without the attribute).

- [ ] **Step 3: Add `order_id` to the `Trade` dataclass**

In `core/types.py`, find the `@dataclass` block for `Trade`. Add `order_id: str | None = None` as the last field. Ensure it's AFTER all non-default fields.

- [ ] **Step 4: Update `core/db.py` insert + fetch**

In `core/db.py`:
- Find `insert_open_trade`. Add `order_id` to the INSERT column list AND the values tuple.
- Find `fetch_open_trades`. Add `order_id` to the SELECT column list AND the row-to-Trade constructor call.

Run `grep -n "insert_open_trade\|fetch_open_trades\|fetch_recent_closed" core/db.py` to locate both functions.

Also check `close_trade`, `fetch_recent_closed`, and any other functions that SELECT from the trades table. Each SELECT needs `order_id` in its column list AND each Trade-construction call needs the new field. Search with `grep -n "Trade(" core/db.py` to find all constructor sites.

- [ ] **Step 5: Run — verify pass + no regression**

```bash
"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/ -v 2>&1 | tail -20
```
Expected: all tests pass, including 41 prior + 2 new = 43 total.

- [ ] **Step 6: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/types.py sports_bot_v2/core/db.py sports_bot_v2/tests/core/test_db_migration.py
git commit -m "sports_bot_v2: Trade.order_id field + db insert/select/fetch support

Trade dataclass gains order_id: str | None = None (defaults to None for paper
trades; populated by live path in Stair C's open_position branch). db insert
and all SELECT-based fetch helpers round-trip the new column.

STAIR_C_LIVE_EXEC_BUILD_001 step 2 of N.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Scaffold `core/signer.py` with `OrderArgs`, `SignedOrder`, `Signer` protocol, `DummySigner`

**Files:**
- Create: `core/signer.py`
- Create: `tests/core/test_signer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_signer.py`:

```python
"""Tests for core.signer — Signer protocol + DummySigner."""
from __future__ import annotations

import pytest


def test_order_args_dataclass_has_expected_fields():
    from core.signer import OrderArgs
    args = OrderArgs(token_id="tok_a", side="BUY", price=0.55, size=50.0)
    assert args.token_id == "tok_a"
    assert args.side == "BUY"
    assert args.price == 0.55
    assert args.size == 50.0
    assert args.order_type == "GTC"  # default


def test_order_args_invalid_side_raises():
    from core.signer import OrderArgs
    with pytest.raises(ValueError):
        OrderArgs(token_id="tok_a", side="NOT_A_SIDE", price=0.5, size=50.0)


def test_signed_order_has_traceable_dummy_tag():
    from core.signer import DummySigner, OrderArgs
    signer = DummySigner()
    args = OrderArgs(token_id="tok_a", side="BUY", price=0.55, size=50.0)
    signed = signer.sign_order(args)

    assert signed.args == args
    assert signed.blob.startswith("dummy:")
    assert signed.signer_tag.startswith("dummy:")
    assert signed.is_dummy is True


def test_dummy_signer_is_not_ready():
    """DummySigner.is_ready() must return False so live_exec refuses to submit
    fake signatures to the real CLOB."""
    from core.signer import DummySigner
    assert DummySigner().is_ready() is False


def test_dummy_signer_produces_unique_blobs():
    """Each sign_order call yields a distinct blob for audit-trail traceability."""
    from core.signer import DummySigner, OrderArgs
    signer = DummySigner()
    args = OrderArgs(token_id="tok_a", side="BUY", price=0.55, size=50.0)
    a = signer.sign_order(args)
    b = signer.sign_order(args)
    assert a.blob != b.blob
```

- [ ] **Step 2: Run — verify fail**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_signer.py -v 2>&1 | tail -15`
Expected: all FAIL with `ModuleNotFoundError: No module named 'core.signer'`.

- [ ] **Step 3: Create `core/signer.py`**

```python
"""
core/signer.py — Order signing protocol + implementations.

This module owns the abstraction boundary between "building an order request"
(public, not sensitive) and "producing a cryptographic signature" (private,
requires a wallet key). Three things live here:

1. `OrderArgs` — pre-sign request dataclass. No crypto.
2. `SignedOrder` — post-sign opaque blob. Real instances carry an EIP-712
   signature py_clob_client can submit; dummy instances carry a traceable fake
   string that will NEVER be accepted by the CLOB.
3. `Signer` — protocol. Two implementations:
   - `DummySigner`: returns traceable fake signatures; is_ready=False so
     live_exec refuses to submit them.
   - `PrivateKeySigner`: fails loudly at __init__ if PRIVATE_KEY env is unset;
     sign_order() is a placeholder (NotImplementedError) for this cycle.
     Real crypto wiring lands in a future Stair C production task.

Why: Stair C builds the code paths "one env-flag flip" away from real live
trading but never activates them. DummySigner lets unit tests exercise every
path WITHOUT ever constructing a real signature.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Literal, Protocol

SideT = Literal["BUY", "SELL"]
OrderTypeT = Literal["GTC", "FOK", "GTD"]
_VALID_SIDES: frozenset[str] = frozenset({"BUY", "SELL"})


@dataclass
class OrderArgs:
    """Pre-signature order request. Pure data — no crypto."""
    token_id: str
    side: SideT
    price: float
    size: float  # USDC notional
    order_type: OrderTypeT = "GTC"

    def __post_init__(self) -> None:
        if self.side not in _VALID_SIDES:
            raise ValueError(f"OrderArgs.side must be BUY or SELL, got {self.side!r}")


@dataclass
class SignedOrder:
    """Post-signature opaque payload. Real instances carry an EIP-712 sig that
    py_clob_client can submit; dummy instances carry a traceable fake."""
    blob: str
    args: OrderArgs
    signer_tag: str  # "dummy:<hex>" or "pk:<0x-addr-prefix>"

    @property
    def is_dummy(self) -> bool:
        return self.signer_tag.startswith("dummy:")


class Signer(Protocol):
    def sign_order(self, args: OrderArgs) -> SignedOrder: ...
    def is_ready(self) -> bool: ...


class DummySigner:
    """Returns structurally-valid fake signatures for build/test paths.
    CLOB will reject them — is_ready() returns False so live_exec never submits."""

    def sign_order(self, args: OrderArgs) -> SignedOrder:
        tag = f"dummy:{uuid.uuid4().hex[:8]}"
        return SignedOrder(
            blob=f"dummy:{uuid.uuid4().hex}",
            args=args,
            signer_tag=tag,
        )

    def is_ready(self) -> bool:
        return False
```

- [ ] **Step 4: Run — verify pass**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_signer.py -v 2>&1 | tail -15`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/signer.py sports_bot_v2/tests/core/test_signer.py
git commit -m "sports_bot_v2: signer.py — OrderArgs, SignedOrder, Signer protocol, DummySigner

Introduces the abstraction boundary between build-time order construction
and crypto signing. DummySigner returns traceable fake blobs (dummy:<hex>)
for tests; is_ready() returns False so live_exec refuses to submit them.
PrivateKeySigner + factory added in subsequent tasks.

STAIR_C_LIVE_EXEC_BUILD_001 step 3 of N.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Add `PrivateKeySigner` (fail-loud) + `get_signer()` factory

**Files:**
- Modify: `core/signer.py`
- Modify: `tests/core/test_signer.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/core/test_signer.py`:

```python
def test_private_key_signer_fails_loud_without_key(monkeypatch):
    """PrivateKeySigner.__init__ MUST raise if PRIVATE_KEY env is missing."""
    monkeypatch.delenv("PRIVATE_KEY", raising=False)
    from core.signer import PrivateKeySigner
    with pytest.raises(RuntimeError, match="PRIVATE_KEY"):
        PrivateKeySigner()


def test_private_key_signer_inits_with_key(monkeypatch):
    """With PRIVATE_KEY set, constructor succeeds. sign_order is still NotImplemented
    this cycle (real crypto wiring deferred)."""
    monkeypatch.setenv("PRIVATE_KEY", "0x" + "a" * 64)  # 32-byte hex
    from core.signer import PrivateKeySigner
    signer = PrivateKeySigner()
    assert signer.is_ready() is True


def test_private_key_signer_sign_order_not_implemented_this_cycle(monkeypatch):
    """Real signing is deferred until a future Stair C production task. For now
    calling sign_order on PrivateKeySigner raises NotImplementedError so nobody
    accidentally wires it up live."""
    monkeypatch.setenv("PRIVATE_KEY", "0x" + "b" * 64)
    from core.signer import PrivateKeySigner, OrderArgs
    signer = PrivateKeySigner()
    args = OrderArgs(token_id="tok_a", side="BUY", price=0.55, size=50.0)
    with pytest.raises(NotImplementedError, match="deferred"):
        signer.sign_order(args)


def test_get_signer_returns_dummy_by_default(monkeypatch):
    monkeypatch.delenv("SIGNER", raising=False)
    from core.signer import get_signer, DummySigner
    s = get_signer()
    assert isinstance(s, DummySigner)


def test_get_signer_respects_env(monkeypatch):
    monkeypatch.setenv("SIGNER", "dummy")
    from core.signer import get_signer, DummySigner
    assert isinstance(get_signer(), DummySigner)


def test_get_signer_private_key_mode(monkeypatch):
    monkeypatch.setenv("SIGNER", "private_key")
    monkeypatch.setenv("PRIVATE_KEY", "0x" + "c" * 64)
    from core.signer import get_signer, PrivateKeySigner
    assert isinstance(get_signer(), PrivateKeySigner)


def test_get_signer_unknown_raises(monkeypatch):
    monkeypatch.setenv("SIGNER", "bogus")
    from core.signer import get_signer
    with pytest.raises(ValueError, match="bogus"):
        get_signer()
```

- [ ] **Step 2: Run — verify fail**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_signer.py -v 2>&1 | tail -15`
Expected: 7 new tests fail (attribute/class missing).

- [ ] **Step 3: Add `PrivateKeySigner` + `get_signer()` to `core/signer.py`**

Append to the end of `core/signer.py`:

```python
class PrivateKeySigner:
    """Signs orders using PRIVATE_KEY env var via eth-account / py_clob_client.

    Constructor raises if PRIVATE_KEY is unset — fail-loud, never silently
    fall back. sign_order() is intentionally NotImplementedError this cycle
    so nobody accidentally wires real signing without completing the production
    Stair C task (which must also verify wallet funding, rate limits, and
    add a kill-switch test with live CLOB).
    """

    def __init__(self) -> None:
        key = os.getenv("PRIVATE_KEY", "").strip()
        if not key:
            raise RuntimeError(
                "PrivateKeySigner: PRIVATE_KEY env var is required. "
                "If you're not ready to go live, use SIGNER=dummy instead."
            )
        self._key = key

    def sign_order(self, args: OrderArgs) -> SignedOrder:
        raise NotImplementedError(
            "Real crypto signing deferred. This code path exists to keep the "
            "structural flip-to-live possible in a future task."
        )

    def is_ready(self) -> bool:
        return True


def get_signer() -> Signer:
    """Factory reads SIGNER env var. Defaults to 'dummy' so nothing ever
    risks submitting a real signature without explicit opt-in."""
    name = os.getenv("SIGNER", "dummy").strip().lower()
    if name == "dummy":
        return DummySigner()
    if name == "private_key":
        return PrivateKeySigner()
    raise ValueError(f"Unknown SIGNER={name!r}; expected 'dummy' or 'private_key'")
```

- [ ] **Step 4: Run — verify pass**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_signer.py -v 2>&1 | tail -20`
Expected: 12 passed (5 prior + 7 new).

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/signer.py sports_bot_v2/tests/core/test_signer.py
git commit -m "sports_bot_v2: signer — PrivateKeySigner scaffold + get_signer factory

PrivateKeySigner.__init__ fails loud if PRIVATE_KEY missing. sign_order()
intentionally NotImplementedError — real crypto wiring is a separate future
task that must also verify wallet funding + add a live-CLOB kill-switch test.
get_signer() factory routes via SIGNER env, defaulting to dummy.

STAIR_C_LIVE_EXEC_BUILD_001 step 4 of N.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Scaffold `core/live_exec.py` with `place_order` + dual-gate kill-switches

**Files:**
- Create: `core/live_exec.py`
- Create: `tests/core/test_live_exec.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_live_exec.py`:

```python
"""Tests for core.live_exec — order placement with dual-gate kill-switches."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_place_order_rejects_in_paper_phase(monkeypatch):
    """PHASE != 'live' → immediate reject before any signer work."""
    monkeypatch.setenv("PHASE", "paper")
    monkeypatch.setenv("LIVE_TRADING_KILL_SWITCH", "false")
    import importlib, core.live_exec
    importlib.reload(core.live_exec)
    result = core.live_exec.place_order(side="BUY", token_id="tok_a", price=0.55, size_usd=50.0)
    assert result.status == "rejected"
    assert result.reason == "phase=paper"
    assert result.order_id is None


def test_place_order_rejects_when_kill_switch_engaged(monkeypatch):
    """PHASE=live + kill-switch=true → reject with reason='kill_switch'."""
    monkeypatch.setenv("PHASE", "live")
    monkeypatch.setenv("LIVE_TRADING_KILL_SWITCH", "true")
    import importlib, core.live_exec
    importlib.reload(core.live_exec)
    result = core.live_exec.place_order(side="BUY", token_id="tok_a", price=0.55, size_usd=50.0)
    assert result.status == "rejected"
    assert result.reason == "kill_switch"
    assert result.order_id is None


def test_place_order_rejects_when_dummy_signer(monkeypatch):
    """Both gates open + DummySigner passed → reject with reason='signer_not_ready'.
    Ensures a dummy signature never reaches post_order."""
    monkeypatch.setenv("PHASE", "live")
    monkeypatch.setenv("LIVE_TRADING_KILL_SWITCH", "false")
    import importlib, core.live_exec
    importlib.reload(core.live_exec)
    from core.signer import DummySigner
    with patch("core.live_exec.tick_size", return_value=0.01):
        result = core.live_exec.place_order(
            side="BUY", token_id="tok_a", price=0.55, size_usd=50.0,
            signer=DummySigner(),
        )
    assert result.status == "rejected"
    assert result.reason == "signer_not_ready"
    assert result.price_snapped == 0.55


def test_place_order_default_signer_is_dummy(monkeypatch):
    """If caller passes no signer and SIGNER env is unset, we get DummySigner →
    reject. This is the critical safety-net: no env misconfig ever lets a
    fake signature reach the network."""
    monkeypatch.setenv("PHASE", "live")
    monkeypatch.setenv("LIVE_TRADING_KILL_SWITCH", "false")
    monkeypatch.delenv("SIGNER", raising=False)
    import importlib, core.live_exec
    importlib.reload(core.live_exec)
    with patch("core.live_exec.tick_size", return_value=0.01):
        result = core.live_exec.place_order(
            side="BUY", token_id="tok_a", price=0.55, size_usd=50.0,
        )
    assert result.status == "rejected"
    assert result.reason == "signer_not_ready"
```

- [ ] **Step 2: Run — verify fail**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_live_exec.py -v 2>&1 | tail -15`
Expected: `ModuleNotFoundError: core.live_exec`.

- [ ] **Step 3: Create `core/live_exec.py`**

```python
"""
core/live_exec.py — Signed-order placement + cancellation.

Dead code during this cycle. Two independent environment flags must BOTH be
flipped for any real order to leave the box:

  PHASE=live                     (default "paper")
  LIVE_TRADING_KILL_SWITCH=false (default "true")

Additionally, the signer returned by core.signer.get_signer() must have
is_ready() == True. The default DummySigner is_ready() == False, so even
if both env flags are flipped, a misconfigured SIGNER value (or the env-
var-missing case) produces a rejected result rather than a real submission.

All rejects log at WARN with the specific gate that tripped, for audit.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from core.polymarket_client import tick_size
from core.signer import OrderArgs, Signer, get_signer

logger = logging.getLogger("core.live_exec")

PHASE = os.getenv("PHASE", "paper").strip().lower()
LIVE_TRADING_KILL_SWITCH = os.getenv("LIVE_TRADING_KILL_SWITCH", "true").strip().lower() in {
    "1", "true", "yes", "on"
}

_MIN_PRICE = 0.01
_MAX_PRICE = 0.99


@dataclass
class OrderResult:
    status: str  # "placed" | "rejected" | "error"
    order_id: str | None
    reason: str
    price_snapped: float | None


def _snap_to_tick(price: float, tick: float) -> float:
    """Round price to the nearest multiple of tick. Clamps float precision."""
    if tick <= 0:
        tick = 0.01
    return round(round(price / tick) * tick, 6)


def _normalize_side(s: str) -> str:
    s = s.strip().upper()
    if s in ("BUY_YES", "BUY_NO", "BUY"):
        return "BUY"
    if s == "SELL":
        return "SELL"
    raise ValueError(f"unknown side: {s!r}")


def place_order(
    side: str,
    token_id: str,
    price: float,
    size_usd: float,
    signer: Signer | None = None,
) -> OrderResult:
    """Place a live order. See module docstring for safety gates.

    Returns an OrderResult with status one of:
      - "placed": real order submitted (never this cycle)
      - "rejected": blocked by one of the kill-switches or signer-not-ready
      - "error": attempted submit but post_order raised
    """
    # Gate 1 — PHASE
    if PHASE != "live":
        return OrderResult(status="rejected", order_id=None, reason=f"phase={PHASE}", price_snapped=None)

    # Gate 2 — kill switch
    if LIVE_TRADING_KILL_SWITCH:
        logger.warning("live_exec.place_order: blocked by LIVE_TRADING_KILL_SWITCH")
        return OrderResult(status="rejected", order_id=None, reason="kill_switch", price_snapped=None)

    # Snap price to tick grid
    tick = tick_size(token_id)
    snapped_price = _snap_to_tick(price, tick)
    if snapped_price < _MIN_PRICE or snapped_price > _MAX_PRICE:
        return OrderResult(
            status="rejected", order_id=None,
            reason=f"price_out_of_band:{snapped_price}", price_snapped=snapped_price,
        )

    # Resolve signer and check readiness
    if signer is None:
        signer = get_signer()
    if not signer.is_ready():
        logger.warning("live_exec.place_order: signer not ready (DummySigner?); refusing submit")
        return OrderResult(
            status="rejected", order_id=None,
            reason="signer_not_ready", price_snapped=snapped_price,
        )

    # All gates open — sign and submit. (Not exercised this cycle; PrivateKeySigner
    # currently raises NotImplementedError in sign_order.)
    args = OrderArgs(
        token_id=token_id,
        side=_normalize_side(side),
        price=snapped_price,
        size=size_usd,
    )
    signed = signer.sign_order(args)  # raises for PrivateKeySigner this cycle

    # Submit to CLOB. Structure of this call is subject to change when the real
    # PrivateKeySigner path lands; today the statement below is unreachable
    # because sign_order() raised.
    try:
        from core.polymarket_client import _get_client
        client = _get_client()
        resp = client.post_order(signed.blob)
        order_id = resp.get("orderID") if isinstance(resp, dict) else None
    except Exception as exc:
        logger.warning("live_exec.place_order: post_order failed err=%s", exc)
        return OrderResult(
            status="error", order_id=None,
            reason=f"post_order:{exc}", price_snapped=snapped_price,
        )

    logger.info("live_exec.place_order: placed order_id=%s side=%s price=%.4f size=%.2f",
                order_id, args.side, snapped_price, size_usd)
    return OrderResult(status="placed", order_id=order_id, reason="", price_snapped=snapped_price)
```

- [ ] **Step 4: Run — verify pass**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_live_exec.py -v 2>&1 | tail -15`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/live_exec.py sports_bot_v2/tests/core/test_live_exec.py
git commit -m "sports_bot_v2: live_exec.place_order with dual-gate kill-switches

Order placement guarded by two independent env flags (PHASE=live,
LIVE_TRADING_KILL_SWITCH=false) AND a signer.is_ready() check. Default
config yields DummySigner which is_ready()==False, so no misconfig chain
can submit a fake signature. Real post_order() code path present but
unreachable today because PrivateKeySigner.sign_order() raises
NotImplementedError (deferred to a future production task).

STAIR_C_LIVE_EXEC_BUILD_001 step 5 of N.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Price-snap + tick-grid tests for `place_order`

**Files:**
- Modify: `tests/core/test_live_exec.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/core/test_live_exec.py`:

```python
def test_price_snaps_to_tick_grid(monkeypatch):
    """Price 0.5567 with tick 0.01 → 0.56 (rounded to nearest multiple)."""
    monkeypatch.setenv("PHASE", "live")
    monkeypatch.setenv("LIVE_TRADING_KILL_SWITCH", "false")
    import importlib, core.live_exec
    importlib.reload(core.live_exec)
    from core.signer import DummySigner
    with patch("core.live_exec.tick_size", return_value=0.01):
        result = core.live_exec.place_order(
            side="BUY", token_id="tok_a", price=0.5567, size_usd=50.0,
            signer=DummySigner(),
        )
    # Dummy signer rejects but price_snapped reflects the snap
    assert result.price_snapped == 0.56


def test_price_snaps_to_fine_tick_grid(monkeypatch):
    """Price 0.12345 with tick 0.001 → 0.123."""
    monkeypatch.setenv("PHASE", "live")
    monkeypatch.setenv("LIVE_TRADING_KILL_SWITCH", "false")
    import importlib, core.live_exec
    importlib.reload(core.live_exec)
    from core.signer import DummySigner
    with patch("core.live_exec.tick_size", return_value=0.001):
        result = core.live_exec.place_order(
            side="BUY", token_id="tok_a", price=0.12345, size_usd=50.0,
            signer=DummySigner(),
        )
    assert result.price_snapped == 0.123


def test_price_out_of_band_rejected(monkeypatch):
    """A price that snaps to < 0.01 or > 0.99 is rejected without touching signer."""
    monkeypatch.setenv("PHASE", "live")
    monkeypatch.setenv("LIVE_TRADING_KILL_SWITCH", "false")
    import importlib, core.live_exec
    importlib.reload(core.live_exec)
    from core.signer import DummySigner
    with patch("core.live_exec.tick_size", return_value=0.01):
        # 0.005 snaps to 0.0 (invalid)
        result = core.live_exec.place_order(
            side="BUY", token_id="tok_a", price=0.005, size_usd=50.0,
            signer=DummySigner(),
        )
    assert result.status == "rejected"
    assert result.reason.startswith("price_out_of_band")


def test_normalize_side_accepts_bot_convention(monkeypatch):
    """Bot uses BUY_YES/BUY_NO as side strings; _normalize_side collapses to BUY."""
    from core.live_exec import _normalize_side
    assert _normalize_side("BUY_YES") == "BUY"
    assert _normalize_side("BUY_NO") == "BUY"
    assert _normalize_side("BUY") == "BUY"
    assert _normalize_side("SELL") == "SELL"
    with pytest.raises(ValueError):
        _normalize_side("INVALID")
```

- [ ] **Step 2: Run — verify fail**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_live_exec.py -v -k "price_snap or out_of_band or normalize_side" 2>&1 | tail -15`
Expected: 4 new tests pass or fail depending on whether prior Task 6 code already handles them. They SHOULD all pass since Task 6 implemented `_snap_to_tick`, `_normalize_side`, and price-out-of-band check. These tests LOCK IN the behavior.

- [ ] **Step 3: Implementation already present — verify**

No code change needed; Task 6 implemented these paths. Verify by re-reading `core/live_exec.py`.

- [ ] **Step 4: Full file run**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_live_exec.py -v 2>&1 | tail -15`
Expected: 8 total passed.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/tests/core/test_live_exec.py
git commit -m "sports_bot_v2: live_exec — lock in tick-snap and price-band tests

Adds 4 tests covering _snap_to_tick behavior at coarse (0.01) and fine
(0.001) tick grids, out-of-band rejection (< 0.01 or > 0.99 after snap),
and _normalize_side BUY_YES/BUY_NO → BUY convention. All already pass;
this task locks the behavior against future regressions.

STAIR_C_LIVE_EXEC_BUILD_001 step 6 of N.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: `cancel_order` and `cancel_all`

**Files:**
- Modify: `core/live_exec.py`
- Modify: `tests/core/test_live_exec.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/core/test_live_exec.py`:

```python
def test_cancel_order_rejects_in_paper_phase(monkeypatch):
    monkeypatch.setenv("PHASE", "paper")
    import importlib, core.live_exec
    importlib.reload(core.live_exec)
    result = core.live_exec.cancel_order("0xorder_a")
    assert result.status == "rejected"
    assert result.reason.startswith("phase=")


def test_cancel_order_rejects_when_kill_switch_engaged(monkeypatch):
    monkeypatch.setenv("PHASE", "live")
    monkeypatch.setenv("LIVE_TRADING_KILL_SWITCH", "true")
    import importlib, core.live_exec
    importlib.reload(core.live_exec)
    result = core.live_exec.cancel_order("0xorder_a")
    assert result.status == "rejected"
    assert result.reason == "kill_switch"


def test_cancel_all_rejects_in_paper_phase(monkeypatch):
    monkeypatch.setenv("PHASE", "paper")
    import importlib, core.live_exec
    importlib.reload(core.live_exec)
    result = core.live_exec.cancel_all()
    assert result.status == "rejected"
    assert result.reason.startswith("phase=")


def test_cancel_all_rejects_when_kill_switch_engaged(monkeypatch):
    monkeypatch.setenv("PHASE", "live")
    monkeypatch.setenv("LIVE_TRADING_KILL_SWITCH", "true")
    import importlib, core.live_exec
    importlib.reload(core.live_exec)
    result = core.live_exec.cancel_all()
    assert result.status == "rejected"
    assert result.reason == "kill_switch"
```

- [ ] **Step 2: Run — verify fail**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_live_exec.py -v -k "cancel" 2>&1 | tail -15`
Expected: 4 fail with `AttributeError: module 'core.live_exec' has no attribute 'cancel_order'`.

- [ ] **Step 3: Add `cancel_order` + `cancel_all` to `core/live_exec.py`**

Append to `core/live_exec.py`:

```python
def cancel_order(order_id: str) -> OrderResult:
    """Cancel a live order by ID. Same dual-gate guards as place_order."""
    if PHASE != "live":
        return OrderResult(status="rejected", order_id=order_id, reason=f"phase={PHASE}", price_snapped=None)
    if LIVE_TRADING_KILL_SWITCH:
        logger.warning("live_exec.cancel_order: blocked by kill_switch order_id=%s", order_id)
        return OrderResult(status="rejected", order_id=order_id, reason="kill_switch", price_snapped=None)

    try:
        from core.polymarket_client import _get_client
        client = _get_client()
        resp = client.cancel_orders([order_id])
        logger.info("live_exec.cancel_order: ok order_id=%s resp=%r", order_id, resp)
        return OrderResult(status="placed", order_id=order_id, reason="", price_snapped=None)
    except Exception as exc:
        logger.warning("live_exec.cancel_order: failed order_id=%s err=%s", order_id, exc)
        return OrderResult(status="error", order_id=order_id, reason=f"cancel:{exc}", price_snapped=None)


def cancel_all() -> OrderResult:
    """Panic stop: cancel ALL open orders for this wallet. Same dual-gate guards."""
    if PHASE != "live":
        return OrderResult(status="rejected", order_id=None, reason=f"phase={PHASE}", price_snapped=None)
    if LIVE_TRADING_KILL_SWITCH:
        logger.warning("live_exec.cancel_all: blocked by kill_switch")
        return OrderResult(status="rejected", order_id=None, reason="kill_switch", price_snapped=None)

    try:
        from core.polymarket_client import _get_client
        client = _get_client()
        resp = client.cancel_market_orders()  # cancel-all for wallet
        logger.info("live_exec.cancel_all: ok resp=%r", resp)
        return OrderResult(status="placed", order_id=None, reason="", price_snapped=None)
    except Exception as exc:
        logger.warning("live_exec.cancel_all: failed err=%s", exc)
        return OrderResult(status="error", order_id=None, reason=f"cancel_all:{exc}", price_snapped=None)
```

- [ ] **Step 4: Run — verify pass**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_live_exec.py -v 2>&1 | tail -20`
Expected: 12 total passed (8 prior + 4 new).

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/live_exec.py sports_bot_v2/tests/core/test_live_exec.py
git commit -m "sports_bot_v2: live_exec — cancel_order + cancel_all

Both functions ride the same PHASE + LIVE_TRADING_KILL_SWITCH dual-gate
as place_order. Uses py_clob_client cancel_orders([id]) and
cancel_market_orders() — both paths unreachable this cycle since the
kill-switch defaults to engaged.

STAIR_C_LIVE_EXEC_BUILD_001 step 7 of N.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Branch `paper_exec.open_position` on `PHASE`

**Files:**
- Modify: `core/paper_exec.py` (around lines 198-292)
- Modify: `bot_core.py` (around line 780 — caller updated to handle Trade | None)
- Create: `tests/core/test_paper_exec_phase_branch.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_paper_exec_phase_branch.py`:

```python
"""Tests for paper_exec.open_position PHASE branching."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _build_inputs():
    """Minimal Market, Signal, OBSnapshot for open_position."""
    from core.types import Market, Signal, OBSnapshot
    market = Market(
        market_id="0xm1",
        event_slug="evt-mlb-test-2026-04-21",
        slug="mlb-test-2026-04-21",
        question="Test?",
        yes_token_id="tok_yes",
        no_token_id="tok_no",
        start_iso=None, end_iso=None,
        sport="baseball", tournament="mlb",
    )
    signal = Signal(
        side="BUY_YES",
        confidence=0.5,
        fair_value_estimate=0.6,
        reasons=[],
        components={
            "recommended_size_dollars": 10.0,
            "held_outcome_label": "YES",
            "home_team": "A",
            "away_team": "B",
            "tracked_team": "A",
            "model_reasons": [],
        },
    )
    ob = OBSnapshot(
        bid_yes=0.50, ask_yes=0.55, bid_no=0.45, ask_no=0.50,
        spread_yes=0.05, spread_no=0.05,
        depth_top5_usd_yes=500.0, depth_top5_usd_no=500.0,
        imbalance=0.0, micro_ok=True, micro_reason="",
        fetched_at="2026-04-21T00:00:00",
        bid_levels_yes=[{"price": 0.50, "size": 1000.0}],
        ask_levels_yes=[{"price": 0.55, "size": 1000.0}],
        bid_levels_no=[{"price": 0.45, "size": 1000.0}],
        ask_levels_no=[{"price": 0.50, "size": 1000.0}],
    )
    return market, signal, ob


def test_paper_phase_returns_open_trade_unchanged(monkeypatch):
    """Default PHASE=paper: open_position behavior unchanged, returns a Trade
    with status='open' and order_id=None."""
    monkeypatch.setenv("PHASE", "paper")
    import importlib, core.paper_exec
    importlib.reload(core.paper_exec)

    market, signal, ob = _build_inputs()
    trade = core.paper_exec.open_position(market, signal, ob)

    assert trade is not None
    assert trade.status == "open"
    assert trade.order_id is None


def test_live_phase_but_live_rejected_returns_none(monkeypatch):
    """PHASE=live but live_exec returns rejected → open_position returns None
    so the caller skips DB insert."""
    monkeypatch.setenv("PHASE", "live")
    monkeypatch.setenv("LIVE_TRADING_KILL_SWITCH", "true")
    import importlib, core.paper_exec, core.live_exec
    importlib.reload(core.live_exec)
    importlib.reload(core.paper_exec)

    market, signal, ob = _build_inputs()
    trade = core.paper_exec.open_position(market, signal, ob)

    assert trade is None


def test_live_phase_placed_annotates_order_id(monkeypatch):
    """PHASE=live + live_exec returns status='placed' → trade.status='pending',
    trade.order_id populated from OrderResult."""
    monkeypatch.setenv("PHASE", "live")
    monkeypatch.setenv("LIVE_TRADING_KILL_SWITCH", "false")
    monkeypatch.setenv("SIGNER", "dummy")
    import importlib, core.paper_exec, core.live_exec
    importlib.reload(core.live_exec)
    importlib.reload(core.paper_exec)

    market, signal, ob = _build_inputs()

    # Inject a fake live_exec.place_order that returns placed
    from core.live_exec import OrderResult
    fake_result = OrderResult(status="placed", order_id="0xlive_abc", reason="", price_snapped=0.55)
    with patch("core.paper_exec._live_place_order", return_value=fake_result):
        trade = core.paper_exec.open_position(market, signal, ob)

    assert trade is not None
    assert trade.status == "pending"
    assert trade.order_id == "0xlive_abc"
```

- [ ] **Step 2: Run — verify fail**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_paper_exec_phase_branch.py -v 2>&1 | tail -20`
Expected: all fail — `_live_place_order` not defined in paper_exec; no PHASE branching.

- [ ] **Step 3: Modify `core/paper_exec.py`**

At the top of `core/paper_exec.py`, after existing imports, add:

```python
PHASE = os.getenv("PHASE", "paper").strip().lower()


def _live_place_order(*args, **kwargs):
    """Indirection layer so tests can patch the live-path call site without
    importing core.live_exec at module load time (avoids bootstrapping issues
    if live_exec imports fail and we want paper to still work)."""
    from core.live_exec import place_order
    return place_order(*args, **kwargs)
```

Change `open_position`'s signature to return `Trade | None`:

```python
def open_position(
    market: Market,
    signal: Signal,
    ob: OBSnapshot,
    mode: str = "neutral",
    source: str = "bot",
    drawdown_mult: float = 1.0,
) -> Trade | None:
```

At the end of `open_position`, AFTER the existing `trade = Trade(...)` construction and BEFORE the `return trade` line, add the PHASE branch:

```python
    # PHASE branch — live mode routes through live_exec.place_order
    if PHASE == "live":
        try:
            live_token_id = market.yes_token_id if signal.side == "BUY_YES" else market.no_token_id
            result = _live_place_order(
                side=signal.side,
                token_id=str(live_token_id),
                price=fill_px,
                size_usd=size_usd,
            )
        except Exception as exc:
            logger.warning("open_position: live_exec raised err=%s — skipping trade", exc)
            return None

        if result.status != "placed":
            logger.info("open_position: live_exec rejected reason=%s — skipping trade", result.reason)
            return None

        trade.status = "pending"
        trade.order_id = result.order_id
        trade.reason_open += f" live_order_id={result.order_id}"
```

Then keep `return trade`.

- [ ] **Step 4: Update caller in `bot_core.py` to handle None**

In `bot_core.py`, find the region where `open_position(...)` is called (around line 780 per the prior survey). Current code is:

```python
                        trade = open_position(
                            market=market, signal=_sig, ob=ob, mode=mode_ctx.mode,
                            source="model_bridge",
                        )
```

Wrap the subsequent DB insert in a None check:

```python
                        trade = open_position(
                            market=market, signal=_sig, ob=ob, mode=mode_ctx.mode,
                            source="model_bridge",
                        )
                        if trade is None:
                            logger.info(
                                "BRIDGE: live_exec skipped trade slug=%s — no DB row inserted",
                                market.slug,
                            )
                            continue
```

If there are OTHER call sites of `open_position` (check with `grep -n "open_position(" bot_core.py`), apply the same None-check pattern to each. DO NOT blindly `continue` if the surrounding logic expects a different flow control — read each site first.

- [ ] **Step 5: Run — verify pass**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/ -v 2>&1 | tail -25`
Expected: all tests pass including 3 new phase-branch tests.

Syntax check bot_core.py:
```bash
"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -c "import ast; ast.parse(open('bot_core.py').read()); print('OK')"
```

- [ ] **Step 6: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/paper_exec.py sports_bot_v2/bot_core.py sports_bot_v2/tests/core/test_paper_exec_phase_branch.py
git commit -m "sports_bot_v2: paper_exec.open_position branches on PHASE

Paper mode (default): behavior unchanged — returns Trade with status='open'
and order_id=None.

Live mode: after sizing + fill computation (same as paper for the DB row),
calls live_exec.place_order. On 'placed' sets status='pending' + order_id.
On 'rejected'/'error' or raise, returns None to signal the caller to skip
DB insert. bot_core caller updated to handle None.

Live path is dead code this cycle (dual-gate defaults ensure no real
submission). Tested via DummySigner + patched _live_place_order.

STAIR_C_LIVE_EXEC_BUILD_001 step 8 of N.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Document new env vars in `.env.example` with safety warnings

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Append the new block to `.env.example`**

Open `.env.example`, scroll to the end (or append after the Stair A Polymarket block), and add:

```
# ── Polymarket execution (Stair C) — DO NOT MODIFY WITHOUT READING ALL NOTES ───
# PHASE gates whether paper_exec routes to live_exec at all.
#   paper = local book-walk only (current behavior; no orders ever sent)
#   live  = route through live_exec.place_order (STILL guarded by kill-switch)
# Default 'paper'. NEVER change to 'live' until you have also:
#   1. Set LIVE_TRADING_KILL_SWITCH=false
#   2. Set SIGNER=private_key
#   3. Set PRIVATE_KEY=<funded wallet key>
#   4. Verified balance with account_sync (Stair D)
#   5. Run 10+ $1-size test orders and reconciled results
PHASE=paper

# Second independent gate on live order placement. MUST be true for paper mode.
# Setting false enables real order submission IF PHASE=live AND signer.is_ready().
# Default 'true'. Treat this as the emergency brake: flipping it back to true at
# any time while live immediately halts all new order placement.
LIVE_TRADING_KILL_SWITCH=true

# Signer selection:
#   dummy       = DummySigner, returns fake signatures. is_ready()=False so
#                 live_exec refuses to submit even with both other gates open.
#   private_key = PrivateKeySigner. Requires PRIVATE_KEY env. sign_order() is
#                 intentionally NotImplementedError this cycle (deferred to a
#                 future Stair C production task that adds wallet-funding
#                 verification and a live-CLOB kill-switch test).
# Default 'dummy'. Any other value raises ValueError at get_signer() call.
SIGNER=dummy

# Hex-encoded Polygon EOA private key. ONLY required when SIGNER=private_key.
# Leave commented out for paper operation. Store in .env.secrets (gitignored),
# NOT in .env. Never commit a funded key.
# PRIVATE_KEY=0x...
```

- [ ] **Step 2: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/.env.example
git commit -m "sports_bot_v2: document Stair C env vars with safety warnings

PHASE, LIVE_TRADING_KILL_SWITCH, SIGNER, PRIVATE_KEY. The comment block
spells out the multi-step checklist operators must complete before flipping
PHASE=live. Keeps the 'one flag flip' promise honest while making it
impossible to do accidentally.

STAIR_C_LIVE_EXEC_BUILD_001 step 9 of N.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: Full regression + "zero live calls" proof

**Files:** none; verification only.

- [ ] **Step 1: Full test suite**

```bash
cd "C:/Users/johnny/Desktop/sports_bot_v2"
"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/ -v 2>&1 | tail -30
```
Expected: all tests pass. Count should be ~61 (39 from Stair A + ~22 new Stair C tests).

- [ ] **Step 2: Grep for any accidental live-call path**

Confirm no new code calls `post_order` or `cancel_orders` outside the guarded branches:

```bash
cd "C:/Users/johnny/Desktop/sports_bot_v2"
grep -rn "post_order\|cancel_orders\|cancel_market_orders\|create_and_post_order" --include="*.py" core/ bot_core.py | grep -v test_ | grep -v "^core/live_exec.py"
```
Expected: zero hits outside `core/live_exec.py`. Any other caller is a bug.

- [ ] **Step 3: Import sanity check**

```bash
"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -c "
from core.signer import DummySigner, PrivateKeySigner, get_signer, Signer, OrderArgs, SignedOrder
from core.live_exec import place_order, cancel_order, cancel_all, OrderResult, PHASE, LIVE_TRADING_KILL_SWITCH
from core.paper_exec import open_position, PHASE as pe_phase
print('signer OK')
print('live_exec OK — PHASE=', PHASE, 'KILL_SWITCH=', LIVE_TRADING_KILL_SWITCH)
print('paper_exec OK — PHASE=', pe_phase)
assert PHASE == 'paper', 'default PHASE must be paper'
assert LIVE_TRADING_KILL_SWITCH is True, 'default kill switch must be engaged'
print('defaults OK — nothing goes live without explicit env change')
"
```
Expected: clean import, `defaults OK` line.

- [ ] **Step 4: Bot_core syntax check** (no restart)

```bash
"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -c "import ast; ast.parse(open('bot_core.py').read()); print('bot_core.py OK')"
```
Expected: `bot_core.py OK`.

- [ ] **Step 5: Capture closeout commit + verification doc**

Create `docs/superpowers/plans/2026-04-21-polymarket-stair-c-verification.md` with:

```markdown
# Stair C Live Verification — 2026-04-21

## What was built

- `core/signer.py` — OrderArgs, SignedOrder, Signer protocol, DummySigner, PrivateKeySigner (fail-loud), get_signer factory
- `core/live_exec.py` — place_order, cancel_order, cancel_all with dual-gate (PHASE + LIVE_TRADING_KILL_SWITCH) + signer.is_ready() safety net
- `core/paper_exec.py` — open_position branches on PHASE; live path routes through live_exec, returns None on reject
- `core/db.py` + `core/types.py` — trades table gained order_id column; Trade dataclass gained order_id field
- `core/polymarket_client.py` — atomic thread-safe _save_tick_cache (preflight)

## Live verification

- Bot PID at plan-start: 9056, USE_BATCH_PRICES=true
- Bot restart during Stair C: NOT REQUIRED. All Stair C changes are dead code
  with the default PHASE=paper + LIVE_TRADING_KILL_SWITCH=true. The only
  side-effect for the running bot at its next organic restart will be the
  trades.order_id column migration (idempotent, NULL for all existing rows).

## Tests: {FILL IN pytest summary}

## Zero-live-call grep: {FILL IN result of Task 11 Step 2}

## Defaults proof: {FILL IN result of Task 11 Step 3}
```

Fill in the `{FILL IN ...}` placeholders with actual output from Steps 1-3.

Then commit:

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/docs/superpowers/plans/2026-04-21-polymarket-stair-c-verification.md
git commit -m "sports_bot_v2: Stair C verification — dead-code path proved safe

Confirms all Stair C code exists, unit tests pass, no module outside
live_exec.py reaches a py_clob_client write endpoint, and default env
keeps PHASE=paper with kill-switch engaged.

STAIR_C_LIVE_EXEC_BUILD_001 closeout.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Definition of Done for Stair C

- [ ] `core/signer.py` has `Signer`, `DummySigner`, `PrivateKeySigner`, `get_signer`, `OrderArgs`, `SignedOrder`
- [ ] `core/live_exec.py` has `place_order`, `cancel_order`, `cancel_all`, `OrderResult`
- [ ] Both env flags (`PHASE`, `LIVE_TRADING_KILL_SWITCH`) default to safe values (paper, true)
- [ ] `SIGNER` env defaults to `dummy`; dummy `is_ready()==False` so no misconfig can submit
- [ ] `_save_tick_cache` is thread-safe + atomic (write-temp + Path.replace, serialized by threading.Lock)
- [ ] `trades` table has `order_id TEXT` column; migration is idempotent
- [ ] `Trade` dataclass has `order_id` field; round-trips through db insert + fetch
- [ ] `paper_exec.open_position` returns `Trade | None`; None on live-reject; bot_core caller handles None
- [ ] All tests pass (expected ~61 total)
- [ ] Grep confirms no `post_order`/`cancel_orders` calls outside `core/live_exec.py`
- [ ] `.env.example` documents new vars with safety warnings
- [ ] 11 commits total, one per Task 1-11

## Follow-ups (NOT in this plan; future Stair C production task)

- Implement `PrivateKeySigner.sign_order` via py_clob_client integration
- Add pre-flip human checklist automation: balance fetcher, kill-switch regression test against live CLOB with $1 probe orders
- Wire TRADE event handler (from Stair B's user_stream) to update `trades.actual_fill_px` and flip `status` from `pending` → `open` on real fills
- Add `account_sync` (Stair D) to reconcile `/positions` drift on boot
