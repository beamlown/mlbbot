# Polymarket Stair B (User Streaming) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the user-channel websocket subscriber (`core/user_stream.py`) that receives TRADE and ORDER events for our own orders, updates sqlite `trades.actual_fill_px` and `status` on fill, and logs order lifecycle transitions. Dead code by default — connects only when `USER_STREAM_MIRROR=true` or `PHASE=live`. Extract the shared reconnect/ping loop from `market_stream.py` into `core/ws_utils.py` so both streams share one reconnect implementation.

**Architecture:** Two new modules + one refactor. `ws_utils.py` owns the websocket reconnect loop as a callable helper. `market_stream.py` is refactored to delegate to it with zero behavior change. `user_stream.py` is a new client that parses TRADE/ORDER events and writes to sqlite. `polymarket_auth.py` scaffolds API-credential provisioning (raises in dummy-signer mode). bot_core gates UserStreamClient startup on opt-in env flags.

**Tech Stack:** Python 3.14, `websocket-client 1.9.0` (already used by market_stream), `py_clob_client 0.34.6` (for `create_or_derive_api_key`), `pytest 9.0.2`, `unittest.mock`.

**Spec reference:** `docs/superpowers/specs/2026-04-20-polymarket-integration-design.md` (Stair B section)

**Work-order alias:** `STAIR_B_USER_STREAM_001`. Resolves `STILL_NEEDS_DONE_002.md` item #1 (Polymarket user/fill stream auth unblock) originally raised April 18.

**Prereqs satisfied:**
- Stair A + Stair C landed (HEAD: `c6b98fb`, 77 tests green)
- `core/polymarket_client.py` — typed HTTP facade
- `core/signer.py` — DummySigner + PrivateKeySigner + get_signer factory
- `core/live_exec.py` — live order placement (dead code)
- `core/paper_exec.py::open_position` — PHASE branch
- `trades` table has `order_id TEXT` column
- `Trade` dataclass has `order_id: str | None = None`
- Live bot running PID 9056 in paper mode — file edits only

---

## File Structure

| File | Role | New/Modify |
|---|---|---|
| `core/db.py` | Partial unique index + `fetch_open_trades` WHERE clause → `status IN ('open','pending')`; add `update_trade_fill()` helper | MODIFY |
| `core/ws_utils.py` | Extracted reconnect loop (`run_with_reconnect`) + ping loop helper | **NEW** |
| `core/market_stream.py` | Delegate `_run`/`_ping_loop` to ws_utils; otherwise unchanged | MODIFY |
| `core/user_stream.py` | `UserStreamClient` subscribes to ws/user; TRADE/ORDER event handlers; debug_status | **NEW** |
| `core/polymarket_auth.py` | `provision_api_credentials(signer)` — caches creds to `runtime/polymarket_creds.json`; raises in dummy mode | **NEW** |
| `bot_core.py` | Start UserStreamClient only when `USER_STREAM_MIRROR=true` OR `PHASE=live` | MODIFY |
| `tests/core/test_ws_utils.py` | Reconnect loop unit tests (mocked WebSocketApp) | **NEW** |
| `tests/core/test_user_stream.py` | TRADE + ORDER event parser tests; sqlite round-trip | **NEW** |
| `tests/core/test_polymarket_auth.py` | Dummy-signer raises; success path mocked | **NEW** |
| `tests/core/test_db_pending_rows.py` | Pending-row uniqueness + fetch_open_trades coverage | **NEW** |
| `.env.example` | Document `USER_STREAM_MIRROR` with safety note | MODIFY |
| `runtime/polymarket_creds.json` | Gitignored cred cache (written only in live path) | runtime artifact |

**Decomposition rationale:** `ws_utils` lets both stream clients reuse one proven reconnect implementation (DRY) without coupling them. `polymarket_auth` isolates the wallet-touching code so it can stay unexercised in paper mode.

---

## Task 1: Preflight — pending-row management in db.py (closes task #38)

Before live-mode TRADE events can transition rows from `pending` → `open`, the duplicate-check and fetch-visibility must treat both statuses as live. Currently `insert_open_trade`'s unique index and `fetch_open_trades`'s WHERE clause only match `status='open'`, so a pending row is both (a) invisible to the bot's management loop and (b) doesn't block a duplicate `open` insert on the same slug.

**Files:**
- Modify: `core/db.py` (CREATE INDEX statement ~line 168-170; `fetch_open_trades` ~line 264-275; new `update_trade_fill` helper)
- Create: `tests/core/test_db_pending_rows.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_db_pending_rows.py`:

```python
"""Tests for pending-row management — required for Stair B's TRADE event
handler to reliably find and update pending rows on fill.
"""
from __future__ import annotations

from pathlib import Path

import pytest


def test_fetch_open_trades_includes_pending_rows(tmp_path, monkeypatch):
    """fetch_open_trades must return rows with status='pending' (live orders
    awaiting fill) AS WELL AS status='open' (paper rows or live-filled rows)."""
    db_path = tmp_path / "t.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    import importlib, core.db, core.types
    importlib.reload(core.db)
    importlib.reload(core.types)
    core.db.init_db()

    # One paper-style open row
    t_open = core.types.Trade(
        id=None, ts_open="2026-04-23T10:00:00+00:00", ts_close=None,
        market_slug="mlb-a-2026-04-23", market_id="0xa",
        side="BUY_YES", qty=100.0, entry_px=0.55, exit_px=None,
        pnl_usd=None, fees_usd=1.0, reason_open="", reason_close=None,
        confidence=0.5, mode="neutral", status="open", source="bot",
        actual_fill_px=0.55, order_id=None,
    )
    core.db.insert_open_trade(t_open)

    # One live-style pending row
    t_pending = core.types.Trade(
        id=None, ts_open="2026-04-23T10:01:00+00:00", ts_close=None,
        market_slug="mlb-b-2026-04-23", market_id="0xb",
        side="BUY_NO", qty=50.0, entry_px=0.42, exit_px=None,
        pnl_usd=None, fees_usd=0.5, reason_open="", reason_close=None,
        confidence=0.6, mode="neutral", status="pending", source="live",
        actual_fill_px=0.0, order_id="0xlive_bbb",
    )
    core.db.insert_open_trade(t_pending)

    rows = core.db.fetch_open_trades()
    slugs = {r.market_slug for r in rows}
    assert "mlb-a-2026-04-23" in slugs, "open row missing"
    assert "mlb-b-2026-04-23" in slugs, "pending row missing — fetch WHERE needs IN ('open','pending')"


def test_update_trade_fill_transitions_pending_to_open(tmp_path, monkeypatch):
    """update_trade_fill(order_id, fill_px) must find the pending row by
    order_id, set actual_fill_px + status='open', return the row id."""
    db_path = tmp_path / "t2.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    import importlib, core.db, core.types
    importlib.reload(core.db)
    importlib.reload(core.types)
    core.db.init_db()

    trade = core.types.Trade(
        id=None, ts_open="2026-04-23T10:00:00+00:00", ts_close=None,
        market_slug="mlb-c-2026-04-23", market_id="0xc",
        side="BUY_YES", qty=100.0, entry_px=0.50, exit_px=None,
        pnl_usd=None, fees_usd=0.5, reason_open="", reason_close=None,
        confidence=0.5, mode="neutral", status="pending", source="live",
        actual_fill_px=0.0, order_id="0xlive_ccc",
    )
    core.db.insert_open_trade(trade)

    updated_id = core.db.update_trade_fill(order_id="0xlive_ccc", actual_fill_px=0.523)
    assert updated_id is not None, "update_trade_fill should return the row id"

    rows = core.db.fetch_open_trades()
    match = [r for r in rows if r.order_id == "0xlive_ccc"]
    assert len(match) == 1
    assert match[0].actual_fill_px == 0.523
    assert match[0].status == "open"


def test_update_trade_fill_returns_none_for_unknown_order(tmp_path, monkeypatch):
    """update_trade_fill on an order_id the DB has never heard of must return
    None (and must NOT create a phantom row)."""
    db_path = tmp_path / "t3.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    import importlib, core.db
    importlib.reload(core.db)
    core.db.init_db()

    result = core.db.update_trade_fill(order_id="0xnot_a_real_order", actual_fill_px=0.5)
    assert result is None
```

- [ ] **Step 2: Run — verify fail**

Run: `cd "C:/Users/johnny/Desktop/sports_bot_v2" && "C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_db_pending_rows.py -v 2>&1 | tail -20`

Expected: `test_fetch_open_trades_includes_pending_rows` FAILS — pending row missing (current WHERE is `status='open'`). The two `update_trade_fill` tests fail with `AttributeError: module 'core.db' has no attribute 'update_trade_fill'`.

- [ ] **Step 3: Fix the partial unique index**

In `core/db.py`, find the CREATE INDEX at line ~168-170. Current:

```python
"CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_one_open_per_slug "
"ON trades(market_slug) WHERE status='open'"
```

Change to:

```python
"CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_one_live_per_slug "
"ON trades(market_slug) WHERE status IN ('open', 'pending')"
```

(Name change to `_one_live_per_slug` reflects the broader scope — one LIVE row per slug instead of just one open row. Old name `_one_open_per_slug` kept as a dead index name only if SQLite drops it automatically via IF NOT EXISTS convention; it will NOT drop; see Step 3b.)

**Step 3b — drop the old index name**

Add a one-line migration call to `init_db`, near the `_migrate_add_order_id_column()` call:

```python
def _migrate_drop_old_open_index(con: sqlite3.Connection) -> None:
    """Drop the pre-Stair-B idx_trades_one_open_per_slug index if present.
    Replaced by idx_trades_one_live_per_slug which covers pending+open."""
    con.execute("DROP INDEX IF EXISTS idx_trades_one_open_per_slug")
    con.commit()
```

Wire it into `init_db`:

```python
    _migrate_add_order_id_column()
    _migrate_drop_old_open_index()
```

(Match the existing migration call pattern — your codebase opens its own connection inside each migration helper; preserve that pattern.)

- [ ] **Step 4: Fix `fetch_open_trades` WHERE clause**

In `core/db.py`, find `fetch_open_trades` (~line 264). Change the SQL WHERE from:

```sql
FROM trades WHERE status='open' ORDER BY id ASC
```

to:

```sql
FROM trades WHERE status IN ('open', 'pending') ORDER BY id ASC
```

Do NOT change `fetch_recent_closed` — that's for closed/resolved trades.

- [ ] **Step 5: Add `update_trade_fill` helper**

Add a new function to `core/db.py`, next to `close_trade` and `update_trade_attribution`:

```python
def update_trade_fill(order_id: str, actual_fill_px: float) -> int | None:
    """Update a pending trade's actual_fill_px and transition status pending→open.

    Called by Stair B's UserStreamClient when a TRADE event arrives. Looks up
    the row by order_id (set when the live-path live_exec.place_order returned
    status='placed'). Returns the row id on success; None if no row matches.
    """
    with _db_conn("update_trade_fill") as conn:
        cur = conn.execute(
            "UPDATE trades SET actual_fill_px=?, status='open' "
            "WHERE order_id=? AND status='pending' "
            "RETURNING id",
            (float(actual_fill_px), str(order_id)),
        )
        row = cur.fetchone()
        return int(row[0]) if row else None
```

- [ ] **Step 6: Run — verify pass + no regression**

```bash
"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/ -v 2>&1 | tail -20
```

Expected: all 77 prior + 3 new = 80 tests pass.

- [ ] **Step 7: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/db.py sports_bot_v2/tests/core/test_db_pending_rows.py
git commit -m "sports_bot_v2: pending-row management — index, fetch, update_trade_fill

Preflight for Stair B: enables TRADE events to find and transition
pending → open rows.

- Unique index renamed from idx_trades_one_open_per_slug to
  idx_trades_one_live_per_slug; predicate widened to
  WHERE status IN ('open','pending'). Drops the old index on boot via
  a new _migrate_drop_old_open_index helper.
- fetch_open_trades WHERE clause widened so pending rows are visible
  to bot management loops.
- New update_trade_fill(order_id, actual_fill_px) helper atomically
  sets fill_px and transitions status='pending' → 'open'. RETURNING id
  so callers can detect no-match (returns None).

Closes tracked task #38. STAIR_B_USER_STREAM_001 prep.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Extract `ws_utils.run_with_reconnect` + tests

Factor the reconnect loop out of `market_stream.py::_run` so `user_stream.py` can reuse it. Keep `_on_open`, `_on_message`, etc. in the client — only the outer loop is shared.

**Files:**
- Create: `core/ws_utils.py`
- Create: `tests/core/test_ws_utils.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_ws_utils.py`:

```python
"""Tests for core.ws_utils.run_with_reconnect."""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest


def test_run_with_reconnect_stops_on_event():
    """When stop_event is set, run_with_reconnect must exit cleanly."""
    from core import ws_utils

    stop_event = threading.Event()
    ws_factory = MagicMock()
    fake_ws = MagicMock()
    fake_ws.run_forever = MagicMock(return_value=None)  # Connection "dropped"
    ws_factory.return_value = fake_ws

    def runner():
        ws_utils.run_with_reconnect(
            ws_factory=ws_factory,
            stop_event=stop_event,
            reconnect_delay=0.01,
            logger_name="test",
        )

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    time.sleep(0.1)  # Let it cycle a few reconnects
    stop_event.set()
    thread.join(timeout=2.0)

    assert not thread.is_alive(), "run_with_reconnect should exit when stop_event set"
    assert ws_factory.call_count >= 1


def test_run_with_reconnect_increments_counter_on_each_reconnect():
    """The on_reconnect callback is invoked each time run_forever returns."""
    from core import ws_utils

    stop_event = threading.Event()
    reconnect_count = {"n": 0}

    def on_reconnect():
        reconnect_count["n"] += 1
        if reconnect_count["n"] >= 3:
            stop_event.set()

    ws_factory = MagicMock()
    fake_ws = MagicMock()
    fake_ws.run_forever = MagicMock(return_value=None)
    ws_factory.return_value = fake_ws

    ws_utils.run_with_reconnect(
        ws_factory=ws_factory,
        stop_event=stop_event,
        reconnect_delay=0.01,
        on_reconnect=on_reconnect,
        logger_name="test",
    )

    assert reconnect_count["n"] >= 3


def test_run_with_reconnect_swallows_run_forever_exceptions():
    """An exception from run_forever must be caught, logged, and followed by
    another reconnect attempt — not propagate out and kill the worker thread."""
    from core import ws_utils

    stop_event = threading.Event()
    call_count = {"n": 0}

    def exploding_run_forever(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] >= 2:
            stop_event.set()
            return None
        raise ConnectionError("simulated network hiccup")

    ws_factory = MagicMock()
    fake_ws = MagicMock()
    fake_ws.run_forever = exploding_run_forever
    ws_factory.return_value = fake_ws

    ws_utils.run_with_reconnect(
        ws_factory=ws_factory,
        stop_event=stop_event,
        reconnect_delay=0.01,
        logger_name="test",
    )

    # Second call succeeded after first raised — proves exception swallowed
    assert call_count["n"] >= 2


def test_run_with_reconnect_sleeps_between_reconnects(monkeypatch):
    """Between reconnect attempts, time.sleep is called with reconnect_delay."""
    from core import ws_utils

    stop_event = threading.Event()
    sleeps: list[float] = []

    def fake_sleep(secs):
        sleeps.append(secs)
        if len(sleeps) >= 2:
            stop_event.set()

    monkeypatch.setattr(ws_utils.time, "sleep", fake_sleep)

    ws_factory = MagicMock()
    fake_ws = MagicMock()
    fake_ws.run_forever = MagicMock(return_value=None)
    ws_factory.return_value = fake_ws

    ws_utils.run_with_reconnect(
        ws_factory=ws_factory,
        stop_event=stop_event,
        reconnect_delay=5.0,
        logger_name="test",
    )

    assert sleeps and sleeps[0] == 5.0
```

- [ ] **Step 2: Run — verify fail**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_ws_utils.py -v 2>&1 | tail -15`

Expected: all FAIL — `ModuleNotFoundError: No module named 'core.ws_utils'`.

- [ ] **Step 3: Create `core/ws_utils.py`**

```python
"""
core/ws_utils.py — Shared websocket reconnect loop.

Extracted from market_stream.py::_run. Both MarketStreamClient and
UserStreamClient (Stair B) delegate their outer reconnect loop here so
there's one proven implementation of the pattern.

The client owns:
  - Building its own `WebSocketApp` (on_open/on_message/on_error/on_close closures)
  - Its own subscription payload and tracked-asset state

This module owns ONLY the "call run_forever, reconnect on return/exception,
respect stop_event" loop.
"""
from __future__ import annotations

import logging
import time
from typing import Callable

import websocket  # noqa: F401  — imported for type-hint clarity in callers


def run_with_reconnect(
    *,
    ws_factory: Callable[[], "websocket.WebSocketApp"],
    stop_event,
    reconnect_delay: float = 3.0,
    on_reconnect: Callable[[], None] | None = None,
    logger_name: str = "ws_utils",
) -> None:
    """Run a websocket in a reconnect-until-stopped loop.

    Args:
      ws_factory: called each reconnect; must return a fresh WebSocketApp.
      stop_event: a threading.Event; set it to terminate the loop.
      reconnect_delay: seconds to sleep between reconnects.
      on_reconnect: optional callback invoked after each disconnect, before
                    sleeping. Useful for the caller to increment a counter
                    or update debug_status.
      logger_name: logger namespace for this runner's messages.

    Exceptions raised inside `run_forever` are caught and logged at WARN;
    the loop continues to the next reconnect. Exceptions inside `ws_factory`
    propagate (the caller's subscription state is broken; can't recover).
    """
    logger = logging.getLogger(logger_name)
    while not stop_event.is_set():
        ws = ws_factory()
        try:
            logger.info("%s: run_forever starting", logger_name)
            ws.run_forever()
        except Exception as exc:
            logger.warning("%s: run_forever exception=%s", logger_name, exc)
        if on_reconnect is not None:
            try:
                on_reconnect()
            except Exception as exc:
                logger.warning("%s: on_reconnect callback raised=%s", logger_name, exc)
        if stop_event.is_set():
            break
        time.sleep(reconnect_delay)
```

- [ ] **Step 4: Run — verify pass**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_ws_utils.py -v 2>&1 | tail -15`

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/ws_utils.py sports_bot_v2/tests/core/test_ws_utils.py
git commit -m "sports_bot_v2: ws_utils.run_with_reconnect — extract reconnect loop

Shared helper for MarketStreamClient + UserStreamClient (Stair B). Wraps
run_forever in a reconnect-until-stopped loop; catches run_forever
exceptions; calls on_reconnect callback between attempts; respects a
stop_event for clean shutdown.

Market stream refactored to use this in the next commit.

STAIR_B_USER_STREAM_001 step 2 of N.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Refactor `market_stream._run` to use `ws_utils.run_with_reconnect`

Zero behavior change. All 17 existing market-stream-adjacent tests (via `test_polymarket_client.py`) + the live bot's runtime behavior stay identical.

**Files:**
- Modify: `core/market_stream.py` (`_run` method, around line 172; keep `_ping_loop` local since it references `self._ws`)

- [ ] **Step 1: Read current `_run` implementation**

Open `core/market_stream.py` lines 172-195. Current shape (approx):

```python
def _run(self) -> None:
    while not self._stop.is_set():
        payload = self._subscription_payload()
        if not payload:
            logger.info("market_stream: no tracked assets, waiting")
            time.sleep(2)
            continue
        self._ws = websocket.WebSocketApp(
            WS_URL,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        ping_thread = threading.Thread(target=self._ping_loop, daemon=True)
        ping_thread.start()
        try:
            logger.info("market_stream: run_forever starting")
            self._ws.run_forever()
        except Exception as exc:
            logger.warning("market_stream: run_forever exception=%s", exc)
        self._reconnect_count += 1
        time.sleep(3)
```

- [ ] **Step 2: Rewrite `_run` to delegate**

Replace the existing `_run` body with:

```python
def _run(self) -> None:
    from core.ws_utils import run_with_reconnect

    def _factory() -> "websocket.WebSocketApp":
        self._ws = websocket.WebSocketApp(
            WS_URL,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        # Start a fresh ping thread each reconnect — old one exited when ws closed
        ping_thread = threading.Thread(target=self._ping_loop, daemon=True)
        ping_thread.start()
        return self._ws

    def _on_reconnect() -> None:
        self._reconnect_count += 1

    # Wait-for-subscription loop is separate from run_with_reconnect because
    # we don't want to connect until there's something to subscribe to.
    while not self._stop.is_set():
        payload = self._subscription_payload()
        if not payload:
            logger.info("market_stream: no tracked assets, waiting")
            time.sleep(2)
            continue
        # Once we have a payload, delegate the reconnect loop. It'll return
        # only when stop is set OR — if we want reconfiguration — when a
        # tracked-assets change triggers ws.close() via update_tracked_assets.
        run_with_reconnect(
            ws_factory=_factory,
            stop_event=self._stop,
            reconnect_delay=3.0,
            on_reconnect=_on_reconnect,
            logger_name="market_stream",
        )
```

- [ ] **Step 3: Run full test suite — verify no regression**

```bash
"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/ -v 2>&1 | tail -15
```
Expected: 80 tests pass (Task 1's 80 preserved).

- [ ] **Step 4: Syntax check + import check**

```bash
cd "C:/Users/johnny/Desktop/sports_bot_v2"
"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -c "from core.market_stream import MarketStreamClient, GLOBAL_MARKET_STREAM; print('market_stream OK')"
```
Expected: `market_stream OK`.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/market_stream.py
git commit -m "sports_bot_v2: market_stream._run delegates to ws_utils.run_with_reconnect

Zero behavior change. The outer reconnect loop is now shared with the
upcoming UserStreamClient (Stair B). _ping_loop stays local to the
client since it references self._ws. The wait-for-subscription loop
stays local too — we don't want to connect until there's a payload.

STAIR_B_USER_STREAM_001 step 3 of N.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Scaffold `core/polymarket_auth.py`

API-credential provisioning via `py_clob_client.ClobClient.create_or_derive_api_key()`. Scaffolded — raises in dummy-signer mode (no real wallet). Used by `UserStreamClient` to auth the user-channel subscription. Not exercised this cycle.

**Files:**
- Create: `core/polymarket_auth.py`
- Create: `tests/core/test_polymarket_auth.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_polymarket_auth.py`:

```python
"""Tests for core.polymarket_auth — API credential provisioning scaffold."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


def test_provision_api_credentials_raises_for_dummy_signer():
    """DummySigner cannot produce real EIP-712 auth signatures → raises.
    Prevents accidental cache-poisoning of runtime/polymarket_creds.json."""
    from core.signer import DummySigner
    from core.polymarket_auth import provision_api_credentials

    with pytest.raises(RuntimeError, match="dummy"):
        provision_api_credentials(DummySigner())


def test_provision_api_credentials_success_path_caches_to_disk(tmp_path, monkeypatch):
    """When a Signer with is_ready()==True is provided, derive creds via
    ClobClient, write them to the cache path, and return them."""
    from core import polymarket_auth

    cache_path = tmp_path / "creds.json"
    monkeypatch.setattr(polymarket_auth, "CREDS_CACHE_PATH", cache_path)

    # A signer that says it's ready — we'll mock the CLOB interaction below
    fake_signer = MagicMock()
    fake_signer.is_ready.return_value = True

    # Mock ClobClient so we don't actually hit the network
    fake_creds = MagicMock()
    fake_creds.api_key = "test_api_key"
    fake_creds.api_secret = "test_api_secret"
    fake_creds.api_passphrase = "test_api_passphrase"
    with patch("core.polymarket_auth.ClobClient") as MockClob:
        MockClob.return_value.create_or_derive_api_key.return_value = fake_creds
        creds = polymarket_auth.provision_api_credentials(fake_signer)

    assert creds["apiKey"] == "test_api_key"
    assert creds["secret"] == "test_api_secret"
    assert creds["passphrase"] == "test_api_passphrase"
    assert cache_path.exists()
    on_disk = json.loads(cache_path.read_text(encoding="utf-8"))
    assert on_disk["apiKey"] == "test_api_key"


def test_provision_api_credentials_loads_from_cache_if_present(tmp_path, monkeypatch):
    """If the cache file exists, return those creds without calling the CLOB."""
    from core import polymarket_auth

    cache_path = tmp_path / "creds.json"
    cache_path.write_text(json.dumps({
        "apiKey": "cached_k", "secret": "cached_s", "passphrase": "cached_p"
    }), encoding="utf-8")
    monkeypatch.setattr(polymarket_auth, "CREDS_CACHE_PATH", cache_path)

    fake_signer = MagicMock()
    fake_signer.is_ready.return_value = True
    with patch("core.polymarket_auth.ClobClient") as MockClob:
        creds = polymarket_auth.provision_api_credentials(fake_signer)

    assert creds["apiKey"] == "cached_k"
    MockClob.assert_not_called()
```

- [ ] **Step 2: Run — verify fail**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_polymarket_auth.py -v 2>&1 | tail -15`

Expected: all 3 FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `core/polymarket_auth.py`**

```python
"""
core/polymarket_auth.py — API credential provisioning for Polymarket user endpoints.

The CLOB's user-channel websocket (ws/user) requires an API key/secret/passphrase
triple. Polymarket derives these from an EOA private key via EIP-712 signed
challenge (py_clob_client.ClobClient.create_or_derive_api_key()).

This module scaffolds that provisioning. In Stair B we never actually call it
with a real signer — DummySigner raises explicitly because its signatures are
not valid EIP-712 payloads; the CLOB would reject them. A future production
task wires PrivateKeySigner to produce a real derive call.

Creds are cached to runtime/polymarket_creds.json (gitignored). The cache
avoids re-deriving on every restart (the derive requires a wallet signature
the operator may not want to repeat).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from py_clob_client.client import ClobClient

from core.signer import DummySigner, Signer

logger = logging.getLogger("core.polymarket_auth")

CLOB_HOST = os.getenv("CLOB_HOST", "https://clob.polymarket.com")
POLYGON_CHAIN_ID = int(os.getenv("POLYGON_CHAIN_ID", "137"))
CREDS_CACHE_PATH = Path(os.getenv("POLYMARKET_CREDS_CACHE_PATH", "runtime/polymarket_creds.json"))


def provision_api_credentials(signer: Signer) -> dict[str, str]:
    """Return cached API creds or derive + cache fresh ones.

    Raises:
        RuntimeError: if signer is a DummySigner — dummy signatures cannot
            produce valid creds; we refuse to even try.
        RuntimeError: if signer.is_ready() is False.
    """
    if isinstance(signer, DummySigner):
        raise RuntimeError(
            "polymarket_auth: DummySigner cannot derive API credentials. "
            "Set SIGNER=private_key + PRIVATE_KEY to enable real derivation."
        )
    if not signer.is_ready():
        raise RuntimeError("polymarket_auth: signer is not ready — cannot derive creds")

    # Cache hit — return without touching the CLOB
    if CREDS_CACHE_PATH.exists():
        try:
            cached = json.loads(CREDS_CACHE_PATH.read_text(encoding="utf-8"))
            if all(k in cached for k in ("apiKey", "secret", "passphrase")):
                logger.info("polymarket_auth: loaded cached creds from %s", CREDS_CACHE_PATH)
                return cached
        except Exception as exc:
            logger.warning("polymarket_auth: cache read failed path=%s err=%s", CREDS_CACHE_PATH, exc)

    # Cache miss — derive via ClobClient. This requires the signer to produce
    # a valid EIP-712 signature; DummySigner would produce garbage. We've
    # already rejected dummy at the top of the function.
    logger.info("polymarket_auth: deriving new API creds via ClobClient")
    client = ClobClient(host=CLOB_HOST, chain_id=POLYGON_CHAIN_ID)  # Signer wiring deferred
    derived = client.create_or_derive_api_key()

    creds = {
        "apiKey": getattr(derived, "api_key", ""),
        "secret": getattr(derived, "api_secret", ""),
        "passphrase": getattr(derived, "api_passphrase", ""),
    }

    try:
        CREDS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CREDS_CACHE_PATH.write_text(json.dumps(creds, indent=2), encoding="utf-8")
        logger.info("polymarket_auth: cached creds to %s", CREDS_CACHE_PATH)
    except Exception as exc:
        logger.warning("polymarket_auth: cache write failed path=%s err=%s", CREDS_CACHE_PATH, exc)

    return creds
```

- [ ] **Step 4: Run — verify pass**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_polymarket_auth.py -v 2>&1 | tail -15`

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/polymarket_auth.py sports_bot_v2/tests/core/test_polymarket_auth.py
git commit -m "sports_bot_v2: polymarket_auth — API credentials scaffold

provision_api_credentials(signer) derives API key/secret/passphrase via
py_clob_client.ClobClient.create_or_derive_api_key(), caches to
runtime/polymarket_creds.json (gitignored), returns cached on subsequent
calls. Raises for DummySigner (can't sign valid EIP-712). Raises if
signer.is_ready() is False.

Unexercised this cycle — real PrivateKeySigner wiring deferred to the
production-Stair-C task.

STAIR_B_USER_STREAM_001 step 4 of N.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Scaffold `core/user_stream.py` with `UserStreamClient` class

Structural skeleton mirroring `MarketStreamClient`. No parsing yet — just start/stop/debug_status/subscription payload. Tests mock `websocket.WebSocketApp`.

**Files:**
- Create: `core/user_stream.py`
- Create: `tests/core/test_user_stream.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_user_stream.py`:

```python
"""Tests for core.user_stream — Polymarket ws/user subscriber."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_user_stream_client_class_exists():
    from core.user_stream import UserStreamClient
    assert UserStreamClient is not None


def test_user_stream_client_debug_status_has_expected_keys():
    from core.user_stream import UserStreamClient
    client = UserStreamClient()
    status = client.debug_status()
    for key in (
        "stream_enabled", "thread_alive", "connected",
        "last_message_ts", "last_message_type",
        "trade_events_seen", "order_events_seen",
        "parser_hit_count", "parser_miss_count", "reconnect_count",
    ):
        assert key in status, f"missing key {key!r}"


def test_user_stream_client_start_without_creds_is_no_op():
    """Calling start() with no configured creds must log+skip, not crash."""
    from core.user_stream import UserStreamClient
    client = UserStreamClient()
    # No creds given. start() should log a warning and return without starting a thread.
    client.start(api_creds=None)
    status = client.debug_status()
    assert status["thread_alive"] is False


def test_user_stream_client_start_with_creds_spawns_thread():
    """start({creds}) spawns the worker thread; stop() stops it."""
    from core.user_stream import UserStreamClient
    client = UserStreamClient()
    with patch("core.user_stream.run_with_reconnect") as mock_run:
        mock_run.return_value = None  # ws finishes immediately
        client.start(api_creds={"apiKey": "k", "secret": "s", "passphrase": "p"})
        # Give the thread a moment to enter run_with_reconnect
        import time as _t
        _t.sleep(0.05)
    client.stop()
```

- [ ] **Step 2: Run — verify fail**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_user_stream.py -v 2>&1 | tail -15`

Expected: all FAIL with `ModuleNotFoundError: core.user_stream`.

- [ ] **Step 3: Create `core/user_stream.py`**

```python
"""
core/user_stream.py — Polymarket user-channel websocket subscriber.

Subscribes to wss://ws-subscriptions-clob.polymarket.com/ws/user with API
credentials derived via polymarket_auth.provision_api_credentials. Receives
TRADE events (our orders got filled) and ORDER events (our order status
changed: new/matched/cancelled/expired).

TRADE handler → db.update_trade_fill(order_id, actual_fill_px) → sqlite row
transitions status='pending' → status='open' with real fill price.
ORDER handler → logs the transition. Row updates from order events are
deferred to a future task (this cycle logs only).

Dead code by default. bot_core only calls UserStreamClient.start() when
USER_STREAM_MIRROR=true OR PHASE=live. With no creds passed or no signer
able to derive them, start() is a warn-and-noop.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

import websocket

from core.ws_utils import run_with_reconnect

logger = logging.getLogger("core.user_stream")

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/user"
PING_INTERVAL_SEC = 10


class UserStreamClient:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._ws: websocket.WebSocketApp | None = None
        self._api_creds: dict[str, str] | None = None
        self._lock = threading.Lock()
        self._connected = False
        self._last_message_ts: float | None = None
        self._last_message_type: str | None = None
        self._trade_events_seen = 0
        self._order_events_seen = 0
        self._parser_hit_count = 0
        self._parser_miss_count = 0
        self._reconnect_count = 0

    def start(self, api_creds: dict[str, str] | None) -> None:
        if not api_creds:
            logger.warning("user_stream: no api_creds provided, start() is a no-op")
            return
        if self._thread and self._thread.is_alive():
            logger.info("user_stream: start skipped, thread already alive")
            return
        self._api_creds = dict(api_creds)
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="user-stream", daemon=True)
        self._thread.start()
        logger.info("user_stream: worker thread started")

    def stop(self) -> None:
        self._stop.set()
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass

    def _subscription_payload(self) -> dict[str, Any] | None:
        if not self._api_creds:
            return None
        return {
            "auth": {
                "apiKey": self._api_creds["apiKey"],
                "secret": self._api_creds["secret"],
                "passphrase": self._api_creds["passphrase"],
            },
            "type": "user",
            "markets": [],  # Empty = subscribe to all user events
        }

    def _on_open(self, ws: websocket.WebSocketApp) -> None:
        self._connected = True
        payload = self._subscription_payload()
        if payload:
            ws.send(json.dumps(payload))
            logger.info("user_stream: subscribed (auth present)")

    def _on_message(self, ws: websocket.WebSocketApp, message: str) -> None:
        try:
            data = json.loads(message)
        except Exception:
            logger.warning("user_stream: non-json message received")
            return
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                self._parser_miss_count += 1
                continue
            event_type = str(item.get("event_type") or item.get("type") or "")
            self._last_message_ts = time.time()
            self._last_message_type = event_type
            if event_type == "PONG":
                continue
            # TRADE and ORDER handlers land in Task 6; today just count.
            self._parser_hit_count += 1

    def _on_error(self, ws: websocket.WebSocketApp, error: Any) -> None:
        logger.warning("user_stream: websocket error=%s", error)

    def _on_close(self, ws: websocket.WebSocketApp, *args: Any) -> None:
        self._connected = False
        logger.warning("user_stream: websocket closed args=%s", args)

    def _run(self) -> None:
        def _factory() -> websocket.WebSocketApp:
            self._ws = websocket.WebSocketApp(
                WS_URL,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )
            ping_thread = threading.Thread(target=self._ping_loop, daemon=True)
            ping_thread.start()
            return self._ws

        def _on_reconnect() -> None:
            self._reconnect_count += 1

        run_with_reconnect(
            ws_factory=_factory,
            stop_event=self._stop,
            reconnect_delay=3.0,
            on_reconnect=_on_reconnect,
            logger_name="user_stream",
        )

    def _ping_loop(self) -> None:
        while not self._stop.is_set() and self._ws:
            try:
                self._ws.send("PING")
            except Exception:
                return
            time.sleep(PING_INTERVAL_SEC)

    def debug_status(self) -> dict[str, Any]:
        return {
            "stream_enabled": True,
            "thread_alive": bool(self._thread and self._thread.is_alive()),
            "connected": self._connected,
            "last_message_ts": self._last_message_ts,
            "last_message_type": self._last_message_type,
            "trade_events_seen": self._trade_events_seen,
            "order_events_seen": self._order_events_seen,
            "parser_hit_count": self._parser_hit_count,
            "parser_miss_count": self._parser_miss_count,
            "reconnect_count": self._reconnect_count,
        }


GLOBAL_USER_STREAM = UserStreamClient()
```

- [ ] **Step 4: Run — verify pass**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_user_stream.py -v 2>&1 | tail -15`

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/user_stream.py sports_bot_v2/tests/core/test_user_stream.py
git commit -m "sports_bot_v2: user_stream.py scaffold

UserStreamClient structure mirrors MarketStreamClient: start/stop,
subscription payload, _on_* callbacks, ping loop, debug_status, delegates
reconnect to ws_utils.run_with_reconnect. Starts only when api_creds
provided to start(); no-op otherwise. TRADE and ORDER event handlers
land in the next task — today _on_message just counts.

STAIR_B_USER_STREAM_001 step 5 of N.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Implement TRADE event handler — updates sqlite via `update_trade_fill`

**Files:**
- Modify: `core/user_stream.py`
- Modify: `tests/core/test_user_stream.py`

Polymarket's `ws/user` TRADE event (per py_clob_client docs) has approximate shape:
```json
{
  "event_type": "trade",
  "id": "<trade_id>",
  "market": "<market_condition_id>",
  "price": "0.5234",
  "size": "100",
  "side": "BUY",
  "status": "MATCHED",
  "maker_orders": [{"order_id": "0xabc", "matched_amount": "50", "price": "0.5234"}, ...]
}
```

We care about: matching the trade back to OUR order via `maker_orders[].order_id`, then calling `update_trade_fill` with the row's actual execution price.

- [ ] **Step 1: Append failing tests**

Append to `tests/core/test_user_stream.py`:

```python
def test_trade_event_updates_sqlite_row(tmp_path, monkeypatch):
    """A TRADE event whose maker_orders[].order_id matches a pending sqlite
    row must trigger update_trade_fill and transition status pending→open."""
    db_path = tmp_path / "t.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    import importlib, core.db, core.types, core.user_stream
    importlib.reload(core.db)
    importlib.reload(core.types)
    importlib.reload(core.user_stream)
    core.db.init_db()

    # Insert a pending row whose order_id will be matched by the event
    trade = core.types.Trade(
        id=None, ts_open="2026-04-23T10:00:00+00:00", ts_close=None,
        market_slug="mlb-x-2026-04-23", market_id="0xmk",
        side="BUY_YES", qty=100.0, entry_px=0.50, exit_px=None,
        pnl_usd=None, fees_usd=0.5, reason_open="", reason_close=None,
        confidence=0.5, mode="neutral", status="pending", source="live",
        actual_fill_px=0.0, order_id="0xlive_xyz",
    )
    core.db.insert_open_trade(trade)

    client = core.user_stream.UserStreamClient()
    fake_event = json.dumps({
        "event_type": "trade",
        "id": "t_xyz",
        "market": "0xmk",
        "price": "0.5234",
        "size": "100",
        "side": "BUY",
        "status": "MATCHED",
        "maker_orders": [{"order_id": "0xlive_xyz", "matched_amount": "100", "price": "0.5234"}],
    })

    client._on_message(None, fake_event)

    rows = [r for r in core.db.fetch_open_trades() if r.order_id == "0xlive_xyz"]
    assert len(rows) == 1
    assert rows[0].status == "open"
    assert rows[0].actual_fill_px == 0.5234
    assert client.debug_status()["trade_events_seen"] == 1


def test_trade_event_with_unknown_order_id_no_ops(tmp_path, monkeypatch):
    """A TRADE event whose maker_orders don't match any row must increment the
    trade_events_seen counter but NOT create or modify any rows."""
    db_path = tmp_path / "t2.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    import importlib, core.db, core.user_stream
    importlib.reload(core.db)
    importlib.reload(core.user_stream)
    core.db.init_db()

    client = core.user_stream.UserStreamClient()
    fake_event = json.dumps({
        "event_type": "trade",
        "market": "0xmk",
        "price": "0.50",
        "maker_orders": [{"order_id": "0xnobody_knows", "matched_amount": "100", "price": "0.50"}],
    })
    client._on_message(None, fake_event)

    assert core.db.fetch_open_trades() == []
    assert client.debug_status()["trade_events_seen"] == 1
```

- [ ] **Step 2: Run — verify fail**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_user_stream.py -v -k "trade_event" 2>&1 | tail -15`

Expected: 2 FAIL — `_on_message` doesn't yet branch on event_type and `trade_events_seen` stays at 0.

- [ ] **Step 3: Extend `_on_message` with TRADE handler**

Open `core/user_stream.py`. Add these imports at the top (alongside existing):

```python
from core.db import update_trade_fill
```

Replace the `_on_message` method with:

```python
    def _on_message(self, ws, message: str) -> None:
        try:
            data = json.loads(message)
        except Exception:
            logger.warning("user_stream: non-json message received")
            return
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                self._parser_miss_count += 1
                continue
            event_type = str(item.get("event_type") or item.get("type") or "").lower()
            self._last_message_ts = time.time()
            self._last_message_type = event_type
            if event_type == "pong":
                continue
            if event_type == "trade":
                self._handle_trade(item)
                self._trade_events_seen += 1
                self._parser_hit_count += 1
            elif event_type == "order":
                self._handle_order(item)
                self._order_events_seen += 1
                self._parser_hit_count += 1
            else:
                self._parser_miss_count += 1

    def _handle_trade(self, event: dict) -> None:
        """Match TRADE event back to our sqlite pending row via maker_orders[].order_id."""
        makers = event.get("maker_orders") or []
        if not isinstance(makers, list):
            logger.warning("user_stream: trade event has non-list maker_orders: %r", event)
            return
        # Event-level price as fallback fill price
        event_price = _to_float(event.get("price"))
        for maker in makers:
            if not isinstance(maker, dict):
                continue
            order_id = str(maker.get("order_id") or "")
            if not order_id:
                continue
            # Prefer the maker's own price if present
            fill_px = _to_float(maker.get("price")) or event_price
            if fill_px is None:
                logger.warning("user_stream: trade event for order=%s has no parseable price", order_id)
                continue
            row_id = update_trade_fill(order_id=order_id, actual_fill_px=fill_px)
            if row_id is not None:
                logger.info(
                    "user_stream: TRADE order_id=%s fill_px=%.4f row_id=%d",
                    order_id, fill_px, row_id,
                )
            else:
                logger.info(
                    "user_stream: TRADE order_id=%s unknown — no row matched",
                    order_id,
                )

    def _handle_order(self, event: dict) -> None:
        """Log ORDER status transitions. Row updates deferred to future task."""
        order_id = str(event.get("id") or event.get("order_id") or "")
        status = str(event.get("status") or "").upper()
        logger.info("user_stream: ORDER order_id=%s status=%s", order_id, status)
```

Also add a module-level helper (mirror of the one in market_stream):

```python
def _to_float(v: Any) -> float | None:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None
```

- [ ] **Step 4: Run — verify pass**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_user_stream.py -v 2>&1 | tail -15`

Expected: 6 passed (4 scaffold + 2 TRADE).

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/user_stream.py sports_bot_v2/tests/core/test_user_stream.py
git commit -m "sports_bot_v2: user_stream TRADE event handler — update sqlite on fill

_on_message now branches on event_type. TRADE events look up the row via
maker_orders[].order_id and call db.update_trade_fill(order_id, price)
to transition status pending→open with the real fill price. Unknown
order_ids log and no-op (trade_events_seen still increments for audit).
ORDER handler added as a log-only stub — persistence deferred to a
follow-up.

Dead code by default. Live bot PID 9056 untouched.

STAIR_B_USER_STREAM_001 step 6 of N.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: ORDER event handler — lock in log format

**Files:**
- Modify: `tests/core/test_user_stream.py`

ORDER handler already exists from Task 6 as a log-only stub. This task pins its behavior.

- [ ] **Step 1: Append test**

Append to `tests/core/test_user_stream.py`:

```python
def test_order_event_increments_counter(caplog):
    """ORDER events log but don't update sqlite. Counter must increment."""
    import core.user_stream, logging, json as _json
    client = core.user_stream.UserStreamClient()
    fake_event = _json.dumps({
        "event_type": "order",
        "id": "0xmy_order",
        "status": "MATCHED",
    })
    with caplog.at_level(logging.INFO, logger="core.user_stream"):
        client._on_message(None, fake_event)
    assert client.debug_status()["order_events_seen"] == 1
    # Log must contain the order_id and status
    messages = " ".join(r.message for r in caplog.records)
    assert "0xmy_order" in messages
    assert "MATCHED" in messages
```

- [ ] **Step 2: Run — verify pass (no code change needed)**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_user_stream.py -v -k "order_event" 2>&1 | tail -15`
Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/tests/core/test_user_stream.py
git commit -m "sports_bot_v2: user_stream ORDER event handler — regression test

Locks in the log-only ORDER handler from Task 6: counter increments,
log contains order_id + status. No sqlite side effect — row updates
from order events are deferred.

STAIR_B_USER_STREAM_001 step 7 of N.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Integrate UserStreamClient into bot_core with opt-in flag

`UserStreamClient` instantiated at import time (`GLOBAL_USER_STREAM` at module scope) but only `.start()` called if `USER_STREAM_MIRROR=true` OR `PHASE=live`. Default (neither set) → no connection attempted.

**Files:**
- Modify: `bot_core.py` (near the `GLOBAL_MARKET_STREAM.start()` call ~line 555-562)

- [ ] **Step 1: Read current market_stream startup region**

Open `bot_core.py`, search for `GLOBAL_MARKET_STREAM.start()`. The current shape is approximately:

```python
    try:
        GLOBAL_MARKET_STREAM.start()
        logger.info("market_stream: client started (websocket thread will connect once assets are tracked)")
    except Exception as exc:
        logger.warning("market_stream: start failed: %s", exc)
```

- [ ] **Step 2: Add the USER_STREAM_MIRROR flag + startup block**

Near the top of `bot_core.py` with other `os.getenv(...)` config reads, add:

```python
USER_STREAM_MIRROR = os.getenv("USER_STREAM_MIRROR", "false").strip().lower() in {"1","true","yes","on"}
```

After the `GLOBAL_MARKET_STREAM.start()` block, add:

```python
    # UserStream — opt-in. Connects only when USER_STREAM_MIRROR=true or PHASE=live.
    # Default env → no ws/user connection, no auth attempt, no creds file written.
    try:
        _phase_is_live = os.getenv("PHASE", "paper").strip().lower() == "live"
        if USER_STREAM_MIRROR or _phase_is_live:
            from core.user_stream import GLOBAL_USER_STREAM
            from core.polymarket_auth import provision_api_credentials
            from core.signer import get_signer
            try:
                creds = provision_api_credentials(get_signer())
                GLOBAL_USER_STREAM.start(api_creds=creds)
                logger.info("user_stream: client started (USER_STREAM_MIRROR=%s PHASE=live=%s)",
                            USER_STREAM_MIRROR, _phase_is_live)
            except RuntimeError as exc:
                logger.info("user_stream: not starting (%s)", exc)
        else:
            logger.info("user_stream: disabled (default) — set USER_STREAM_MIRROR=true to enable")
    except Exception as exc:
        logger.warning("user_stream: startup failed unexpectedly: %s", exc)
```

Add `"USER_STREAM_MIRROR": USER_STREAM_MIRROR` to the STARTUP_PROOF gates dict so operators can see the flag state in logs.

- [ ] **Step 3: Syntax check**

```bash
cd "C:/Users/johnny/Desktop/sports_bot_v2"
"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -c "import ast; ast.parse(open('bot_core.py').read()); print('OK')"
```
Expected: `OK`.

- [ ] **Step 4: Verify default-off behavior via subprocess**

```bash
"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -c "
import os
os.environ.pop('USER_STREAM_MIRROR', None)
os.environ.pop('PHASE', None)
from bot_core import USER_STREAM_MIRROR
assert USER_STREAM_MIRROR is False, 'default must be False'
print('default USER_STREAM_MIRROR=False: OK')
"
```
Expected: `default USER_STREAM_MIRROR=False: OK`.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/bot_core.py
git commit -m "sports_bot_v2: bot_core — opt-in USER_STREAM_MIRROR startup

UserStreamClient.start() now called only when USER_STREAM_MIRROR=true
OR PHASE=live. Default env → no ws/user connection attempted, no auth
derivation, no polymarket_creds.json written. If provision_api_credentials
raises (DummySigner), startup logs and moves on — paper bot unaffected.

STARTUP_PROOF gates dict now surfaces USER_STREAM_MIRROR so operators can
confirm the flag state from logs on next respawn.

STAIR_B_USER_STREAM_001 step 8 of N.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Document `USER_STREAM_MIRROR` in `.env.example`

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Append block**

Append to `.env.example`, after the Stair C block:

```
# ── Polymarket user stream (Stair B) ──────────────────────────────────────────
# Enable the ws/user subscription to receive TRADE and ORDER events for our
# own orders. Off by default. Also auto-enabled when PHASE=live.
#
# SAFETY: this is the ONLY way to open a ws/user connection. Default 'false'
# means no auth derivation attempt, no API-key file written, no websocket
# opened. Safe for paper operation.
#
# When enabled (and signer is real), the bot derives API creds from the
# wallet on first run and caches them to runtime/polymarket_creds.json
# (gitignored). Subsequent runs reuse the cache.
#
# Dummy-signer mode: enabling this flag yields a one-line warning at startup
# ("user_stream: not starting (DummySigner cannot derive...)") and then no-op.
# Paper bot behavior is unaffected.
USER_STREAM_MIRROR=false
```

- [ ] **Step 2: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/.env.example
git commit -m "sports_bot_v2: document USER_STREAM_MIRROR in .env.example

Explains the flag's role (ONLY way to open ws/user connection), the
default-safe behavior, and the dummy-signer no-op fallback. Paired with
Task 8's opt-in startup logic.

STAIR_B_USER_STREAM_001 step 9 of N.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Full regression + zero-connection proof

**Files:** none; verification only.

- [ ] **Step 1: Full test suite**

```bash
cd "C:/Users/johnny/Desktop/sports_bot_v2"
"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/ -v 2>&1 | tail -20
```
Expected: ~91 tests pass (Stair A: 39; Stair C: +38 = 77; Stair B preflight: +3 = 80; Stair B tests: +4 ws_utils + 3 auth + 7 user_stream = 94). Total ≈ 94.

- [ ] **Step 2: Zero-connection grep**

Verify nothing connects to `ws/user` outside `user_stream.py`:

```bash
grep -rn "ws/user\|wss://ws-subscriptions-clob.polymarket.com/ws/user" --include="*.py" core/ bot_core.py | grep -v test_ | grep -v "core/user_stream.py"
```
Expected: empty.

Verify `polymarket_auth.provision_api_credentials` has no callers outside bot_core's opt-in block and user_stream:

```bash
grep -rn "provision_api_credentials" --include="*.py" core/ bot_core.py | grep -v test_
```
Expected: exactly 2 hits — `core/polymarket_auth.py` (definition) and `bot_core.py` (gated call).

- [ ] **Step 3: Import sanity + defaults proof**

```bash
"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -c "
import os
for k in ('PHASE','LIVE_TRADING_KILL_SWITCH','SIGNER','USER_STREAM_MIRROR'):
    os.environ.pop(k, None)
from core.user_stream import UserStreamClient, GLOBAL_USER_STREAM
from core.polymarket_auth import provision_api_credentials
from core.ws_utils import run_with_reconnect
from bot_core import USER_STREAM_MIRROR
assert USER_STREAM_MIRROR is False
status = GLOBAL_USER_STREAM.debug_status()
assert status['thread_alive'] is False, 'user stream thread must not be alive by default'
assert status['connected'] is False, 'user stream must not be connected by default'
print('all Stair B defaults OK — no ws/user connection without explicit opt-in')
"
```
Expected: `all Stair B defaults OK — no ws/user connection without explicit opt-in`.

- [ ] **Step 4: Live bot untouched check**

```bash
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*bot_core.py*' } | Select-Object ProcessId, CreationDate | Format-Table -AutoSize"
```
Confirm the same PID is still running since Stair A/C.

- [ ] **Step 5: Verification doc + commit**

Create `docs/superpowers/plans/2026-04-23-polymarket-stair-b-verification.md`:

```markdown
# Stair B Live Verification — 2026-04-23

## What was built

- **`core/ws_utils.py`** — shared `run_with_reconnect()` helper; extracted from market_stream
- **`core/market_stream.py`** — refactored `_run` to delegate; zero behavior change
- **`core/polymarket_auth.py`** — `provision_api_credentials(signer)` scaffold; raises for DummySigner
- **`core/user_stream.py`** — `UserStreamClient` subscribes to ws/user, TRADE handler updates sqlite via `db.update_trade_fill`, ORDER handler logs lifecycle events
- **`core/db.py`** — partial index widened to `IN ('open','pending')`; `fetch_open_trades` WHERE clause likewise; new `update_trade_fill()` helper
- **`bot_core.py`** — UserStreamClient.start() gated on `USER_STREAM_MIRROR` OR `PHASE=live`; `USER_STREAM_MIRROR` surfaced in STARTUP_PROOF
- **`.env.example`** — `USER_STREAM_MIRROR=false` with safety-first docstring

## Test suite: {FILL IN}

## Zero-connection grep: {FILL IN — expect empty}

## Defaults proof: {FILL IN}

## Live bot status: PID {FILL IN} unchanged

## Commits: {FILL IN the list}

## Closes STILL_NEEDS_DONE_002 item #1 (Polymarket user/fill stream auth) — April 18 work unblocked.
```

Fill in the `{FILL IN ...}` with actual output from Steps 1-4. Commit:

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/docs/superpowers/plans/2026-04-23-polymarket-stair-b-verification.md
git commit -m "sports_bot_v2: Stair B verification — user_stream dead-code-by-default proved

Full test suite green; no ws/user connection fires in default env;
live bot unchanged throughout Stair B. Closes STILL_NEEDS_DONE_002
item #1 originally raised April 18.

STAIR_B_USER_STREAM_001 closeout.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Definition of Done for Stair B

- [ ] `core/ws_utils.run_with_reconnect()` exists; 4 unit tests pass
- [ ] `core/market_stream.py::_run` delegates to `ws_utils`; MarketStreamClient imports + runs the same as before
- [ ] `core/user_stream.py::UserStreamClient` exists with start/stop/debug_status/TRADE handler/ORDER handler
- [ ] `core/polymarket_auth.py::provision_api_credentials()` exists; raises for DummySigner; caches creds to runtime path on success
- [ ] `core/db.py` treats `status IN ('open','pending')` for both duplicate-check index and `fetch_open_trades`
- [ ] `core/db.update_trade_fill(order_id, actual_fill_px)` transitions pending→open
- [ ] `bot_core.py` starts UserStreamClient only when `USER_STREAM_MIRROR=true` OR `PHASE=live`
- [ ] `.env.example` documents `USER_STREAM_MIRROR`
- [ ] Default env (no flags set) → no ws/user connection, no auth derivation, no creds file written
- [ ] Grep confirms `ws/user` URL and `provision_api_credentials` only referenced inside the expected modules
- [ ] All tests pass (expected total ~94)
- [ ] 10 commits, one per task

## Follow-ups (NOT in this plan)

- ORDER event → sqlite persistence (currently log-only). A row for each order transition would support richer dashboards + post-hoc reconciliation with `/orders` history from Stair D.
- PrivateKeySigner wiring (still deferred). When it lands, `provision_api_credentials` actually derives real creds and `UserStreamClient` actually connects with auth.
- Replay harness integration: capture TRADE/ORDER events to JSONL during a live session so the parser can be regression-tested against real Polymarket shapes later.
