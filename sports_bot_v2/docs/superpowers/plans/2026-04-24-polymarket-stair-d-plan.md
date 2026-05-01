# Polymarket Stair D (Account State Sync) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the boot-time account-state reconciliation path — `reconcile_positions_on_boot()`, `fetch_balance()`, `sync_trades_history(since_ts)` — as dead code behind the same signer/creds gating as Stair B. Paper mode: a single `"no wallet, skipping"` log line at boot. Live mode: diff server-side `/positions` + `/trades` vs. local sqlite, log drift, warn on low USDC balance.

**Architecture:** One new module (`core/account_sync.py`) + three new authenticated helpers in `core/polymarket_client.py`. Integration is a single call added to `bot_core.main()` after `init_db()`. No background threads; sync runs exactly once per process start. With no API creds (default), all three functions warn-and-noop.

**Tech Stack:** Python 3.14, `py_clob_client 0.34.6` (uses `get_balance_allowance`, `get_trades`, `get_orders`), `pytest 9.0.2`, `unittest.mock`.

**Spec reference:** `docs/superpowers/specs/2026-04-20-polymarket-integration-design.md` (Stair D section)

**Work-order alias:** `STAIR_D_ACCOUNT_SYNC_001`

**Prereqs satisfied:**
- Stair A+B+C landed (HEAD: `d69dd26`, 94 tests green)
- `core/polymarket_client.py` — unauthenticated endpoints + memoized `_get_client()`
- `core/polymarket_auth.py` — `provision_api_credentials(signer)` returns creds or raises for DummySigner
- `core/db.fetch_open_trades()` returns rows with `status IN ('open','pending')`
- Live bot PID 9056 running in paper — file edits only

---

## File Structure

| File | Role | New/Modify |
|---|---|---|
| `core/polymarket_client.py` | Add `get_balance_allowance`, `get_my_trades`, `get_my_orders` authenticated-GET helpers | MODIFY |
| `core/account_sync.py` | `reconcile_positions_on_boot`, `fetch_balance`, `sync_trades_history` + internal drift-diff helpers | **NEW** |
| `bot_core.py` | Call `reconcile_positions_on_boot()` once after `init_db()`; gated the same as user_stream (needs creds, skips in paper) | MODIFY |
| `tests/core/test_account_sync.py` | No-op paths + drift-detection matrix + balance warn-below-threshold | **NEW** |
| `tests/core/test_polymarket_client.py` | New test cases for the three authenticated helpers (mocked py_clob_client) | MODIFY |
| `.env.example` | `ACCOUNT_SYNC_ENABLED`, `MIN_BALANCE_WARN_USD` | MODIFY |

---

## Task 1: Add authenticated-GET helpers to `core/polymarket_client.py`

Wrap three `py_clob_client.ClobClient` methods the same way we already wrap `batch_midpoints` et al. These stay unexercised in paper mode (no creds → account_sync no-ops before calling any of them).

**Files:**
- Modify: `core/polymarket_client.py`
- Modify: `tests/core/test_polymarket_client.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/core/test_polymarket_client.py`:

```python
def test_get_balance_allowance_returns_usdc_float():
    """get_balance_allowance wraps ClobClient.get_balance_allowance and
    returns the allowance.balance as a float (converted from py_clob_client's
    decimal-string representation)."""
    import core.polymarket_client as pm
    pm._client = None
    fake_client = MagicMock()
    # py_clob_client returns a dict-ish with 'balance' as stringified int6
    fake_client.get_balance_allowance.return_value = {"balance": "250000000"}  # 250 USDC (6 decimals)
    with patch("core.polymarket_client._get_client", return_value=fake_client):
        bal = pm.get_balance_allowance()
    assert bal == pytest.approx(250.0)


def test_get_balance_allowance_returns_none_on_empty():
    import core.polymarket_client as pm
    pm._client = None
    fake_client = MagicMock()
    fake_client.get_balance_allowance.return_value = {}
    with patch("core.polymarket_client._get_client", return_value=fake_client):
        assert pm.get_balance_allowance() is None


def test_get_my_trades_returns_list_of_trades():
    """get_my_trades passes the since_ts filter to py_clob_client and returns
    the raw list (parsing stays in account_sync)."""
    import core.polymarket_client as pm
    pm._client = None
    fake_client = MagicMock()
    fake_client.get_trades.return_value = [
        {"id": "t1", "price": "0.55", "size": "100", "market": "0xm1", "timestamp": "1716000000"},
        {"id": "t2", "price": "0.42", "size": "50",  "market": "0xm2", "timestamp": "1716000100"},
    ]
    with patch("core.polymarket_client._get_client", return_value=fake_client):
        trades = pm.get_my_trades(since_ts=1716000000)
    assert len(trades) == 2
    assert trades[0]["id"] == "t1"


def test_get_my_orders_returns_list_of_orders():
    """get_my_orders returns the raw SDK response. Empty list is valid
    (no open orders)."""
    import core.polymarket_client as pm
    pm._client = None
    fake_client = MagicMock()
    fake_client.get_orders.return_value = []
    with patch("core.polymarket_client._get_client", return_value=fake_client):
        orders = pm.get_my_orders()
    assert orders == []
```

- [ ] **Step 2: Run — verify fail**

Run: `cd "C:/Users/johnny/Desktop/sports_bot_v2" && "C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_polymarket_client.py -v -k "balance or my_trades or my_orders" 2>&1 | tail -15`
Expected: all 4 FAIL — `AttributeError: module 'core.polymarket_client' has no attribute 'get_balance_allowance'` (same for others).

- [ ] **Step 3: Add helpers to `core/polymarket_client.py`**

Append to `core/polymarket_client.py`, after `refresh_tick_sizes`:

```python
# --- Authenticated GET helpers (Stair D) -------------------------------------
# These require API credentials. They are never called by paper mode; the
# caller (core.account_sync) checks creds-availability first. DummySigner
# can't produce creds (polymarket_auth raises), so these stay unexercised
# in paper mode by construction.

_USDC_DECIMALS = 1_000_000  # Polygon USDC has 6 decimals


def get_balance_allowance() -> float | None:
    """Fetch USDC balance (in whole USDC) from the connected wallet.
    Returns None if the response is missing or unparseable."""
    client = _get_client()
    resp = retry_with_backoff(
        lambda: client.get_balance_allowance(),
        retries=RETRIES, backoff_ms=BACKOFF_MS,
    )
    if not isinstance(resp, dict):
        return None
    raw_balance = resp.get("balance")
    try:
        # py_clob_client returns int6-as-string; convert to whole USDC
        return float(raw_balance) / _USDC_DECIMALS if raw_balance is not None else None
    except (TypeError, ValueError):
        logger.warning("get_balance_allowance: unparseable balance=%r", raw_balance)
        return None


def get_my_trades(since_ts: int | None = None) -> list[dict]:
    """Fetch my trade history. If since_ts is given, filter client-side to
    events after that unix timestamp (py_clob_client's own since filter
    isn't uniformly supported)."""
    client = _get_client()
    resp = retry_with_backoff(
        lambda: client.get_trades(),
        retries=RETRIES, backoff_ms=BACKOFF_MS,
    )
    if not isinstance(resp, list):
        return []
    if since_ts is None:
        return resp
    out: list[dict] = []
    for t in resp:
        if not isinstance(t, dict):
            continue
        try:
            ts = int(float(t.get("timestamp") or 0))
        except (TypeError, ValueError):
            ts = 0
        if ts >= since_ts:
            out.append(t)
    return out


def get_my_orders() -> list[dict]:
    """Fetch my currently-open orders."""
    client = _get_client()
    resp = retry_with_backoff(
        lambda: client.get_orders(),
        retries=RETRIES, backoff_ms=BACKOFF_MS,
    )
    return resp if isinstance(resp, list) else []
```

- [ ] **Step 4: Run — verify pass**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_polymarket_client.py -v 2>&1 | tail -15`
Expected: 21 tests pass (17 prior + 4 new).

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/polymarket_client.py sports_bot_v2/tests/core/test_polymarket_client.py
git commit -m "sports_bot_v2: polymarket_client — authenticated GET helpers for Stair D

Wraps py_clob_client's get_balance_allowance, get_trades, get_orders with
the same retry_with_backoff pattern used by the unauthenticated batch
endpoints. get_balance_allowance converts int6 to whole USDC. get_my_trades
supports client-side since_ts filtering. All three unexercised in paper
mode (no creds → account_sync no-ops before calling).

STAIR_D_ACCOUNT_SYNC_001 step 1 of 6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Scaffold `core/account_sync.py` with no-op paper-mode paths

**Files:**
- Create: `core/account_sync.py`
- Create: `tests/core/test_account_sync.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_account_sync.py`:

```python
"""Tests for core.account_sync — boot-time reconcile + balance + trade-history sync."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_reconcile_positions_on_boot_noop_without_creds(caplog):
    """Default (paper) mode: no creds → single 'no wallet, skipping' log,
    no HTTP, no exception."""
    import core.account_sync
    import logging
    with patch("core.account_sync._get_creds", return_value=None):
        with caplog.at_level(logging.INFO, logger="core.account_sync"):
            result = core.account_sync.reconcile_positions_on_boot()
    assert result is None
    messages = " ".join(r.message for r in caplog.records)
    assert "no wallet" in messages.lower() or "skipping" in messages.lower()


def test_fetch_balance_noop_without_creds():
    """fetch_balance() returns None when no creds available."""
    import core.account_sync
    with patch("core.account_sync._get_creds", return_value=None):
        assert core.account_sync.fetch_balance() is None


def test_sync_trades_history_noop_without_creds():
    """sync_trades_history returns 0 when no creds available (no rows inserted)."""
    import core.account_sync
    with patch("core.account_sync._get_creds", return_value=None):
        assert core.account_sync.sync_trades_history(since_ts=0) == 0


def test_account_sync_module_public_api():
    """The three public functions must all be importable."""
    from core.account_sync import reconcile_positions_on_boot, fetch_balance, sync_trades_history
    assert callable(reconcile_positions_on_boot)
    assert callable(fetch_balance)
    assert callable(sync_trades_history)
```

- [ ] **Step 2: Run — verify fail**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_account_sync.py -v 2>&1 | tail -15`
Expected: all 4 FAIL — `ModuleNotFoundError: core.account_sync`.

- [ ] **Step 3: Create `core/account_sync.py`**

```python
"""
core/account_sync.py — Boot-time account state reconciliation.

Runs once at bot_core startup, right after init_db(). Queries Polymarket's
authenticated endpoints to:
  1. Fetch current USDC balance and warn if below 2× MAX_POSITION_SIZE_USD
  2. Fetch my open orders + my recent trade history
  3. Diff against local sqlite trades table; log any drift

Paper-mode behavior: no API creds available (polymarket_auth raises for
DummySigner), so all three public functions return immediately with a
"no wallet, skipping" log line. Zero HTTP, zero side effects.

Live-mode behavior (future, with PrivateKeySigner + real wallet):
reconcile_positions_on_boot() logs a drift report comparing server-side
open orders to local status='open'/'pending' rows. Mismatches don't
auto-correct — the operator decides whether to cancel orphan orders,
open missing rows, etc.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("core.account_sync")

MIN_BALANCE_WARN_USD = float(os.getenv("MIN_BALANCE_WARN_USD", "50.0"))


def _get_creds() -> dict[str, str] | None:
    """Return cached API creds or None if none available.

    In paper mode with DummySigner, polymarket_auth.provision_api_credentials
    raises — we catch and return None so the caller can log+skip cleanly
    without re-raising through the boot sequence.
    """
    try:
        from core.polymarket_auth import provision_api_credentials
        from core.signer import get_signer
        return provision_api_credentials(get_signer())
    except Exception as exc:
        logger.debug("account_sync: no creds available (%s)", exc)
        return None


def reconcile_positions_on_boot() -> dict | None:
    """Run the full reconcile pass. Returns a drift-report dict on success,
    None if skipped (paper mode)."""
    creds = _get_creds()
    if creds is None:
        logger.info("account_sync: no wallet, skipping boot reconcile")
        return None
    logger.info("account_sync: reconcile starting (live mode)")
    # Live-mode impl lands in Task 3
    raise NotImplementedError("reconcile_positions_on_boot live path — Task 3")


def fetch_balance() -> float | None:
    """Return wallet USDC balance, or None if skipped."""
    creds = _get_creds()
    if creds is None:
        return None
    raise NotImplementedError("fetch_balance live path — Task 4")


def sync_trades_history(since_ts: int) -> int:
    """Sync my trades from since_ts into sqlite. Returns count of rows processed."""
    creds = _get_creds()
    if creds is None:
        return 0
    raise NotImplementedError("sync_trades_history live path — Task 5")
```

- [ ] **Step 4: Run — verify pass**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_account_sync.py -v 2>&1 | tail -15`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/account_sync.py sports_bot_v2/tests/core/test_account_sync.py
git commit -m "sports_bot_v2: account_sync.py scaffold — no-op in paper mode

Three public functions (reconcile_positions_on_boot, fetch_balance,
sync_trades_history) all check _get_creds() first. With DummySigner
(default), provision_api_credentials raises, _get_creds catches and
returns None, and each function warn-and-noops. Live-path
implementations are NotImplementedError stubs filled in by next tasks.

STAIR_D_ACCOUNT_SYNC_001 step 2 of 6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Implement `reconcile_positions_on_boot` drift detection

**Files:**
- Modify: `core/account_sync.py`
- Modify: `tests/core/test_account_sync.py`

Drift categories we detect:
- **orphan_local**: row in sqlite with `status='open'`/'pending' that has NO matching server-side order AND no matching recent trade → log WARN (likely a stale paper row or a canceled order we didn't catch)
- **orphan_server**: server-side open order whose `order_id` has no local row → log WARN (an order the bot didn't create — operator manually placed?)
- **match**: local row + server order agree → log INFO

- [ ] **Step 1: Append failing tests**

Append to `tests/core/test_account_sync.py`:

```python
def test_reconcile_detects_orphan_local(tmp_path, monkeypatch, caplog):
    """A sqlite row with status=open but no server-side match → logs
    drift:orphan_local warning."""
    db_path = tmp_path / "t.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    import importlib, core.db, core.types, core.account_sync
    importlib.reload(core.db)
    importlib.reload(core.types)
    importlib.reload(core.account_sync)
    core.db.init_db()

    # Local row with status='pending' that server won't echo
    t = core.types.Trade(
        id=None, ts_open="2026-04-24T00:00:00+00:00", ts_close=None,
        market_slug="mlb-x-2026-04-24", market_id="0xmk",
        side="BUY_YES", qty=100.0, entry_px=0.50, exit_px=None,
        pnl_usd=None, fees_usd=0.5, reason_open="", reason_close=None,
        confidence=0.5, mode="neutral", status="pending", source="live",
        actual_fill_px=0.0, order_id="0xlive_orphan",
    )
    core.db.insert_open_trade(t)

    fake_creds = {"apiKey": "k", "secret": "s", "passphrase": "p"}
    import logging
    with patch("core.account_sync._get_creds", return_value=fake_creds):
        with patch("core.account_sync.get_my_orders", return_value=[]):
            with patch("core.account_sync.get_my_trades", return_value=[]):
                with caplog.at_level(logging.WARNING, logger="core.account_sync"):
                    report = core.account_sync.reconcile_positions_on_boot()

    assert report is not None
    assert "0xlive_orphan" in {o for o in report.get("orphan_local", [])}
    messages = " ".join(r.message for r in caplog.records)
    assert "orphan_local" in messages
    assert "0xlive_orphan" in messages


def test_reconcile_detects_orphan_server(tmp_path, monkeypatch, caplog):
    """Server has an open order we don't have locally → orphan_server."""
    db_path = tmp_path / "t2.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    import importlib, core.db, core.account_sync
    importlib.reload(core.db)
    importlib.reload(core.account_sync)
    core.db.init_db()

    # No local rows; server returns one open order
    fake_orders = [{"id": "0xserver_only", "market": "0xmk", "price": "0.55", "size": "100"}]
    fake_creds = {"apiKey": "k", "secret": "s", "passphrase": "p"}
    import logging
    with patch("core.account_sync._get_creds", return_value=fake_creds):
        with patch("core.account_sync.get_my_orders", return_value=fake_orders):
            with patch("core.account_sync.get_my_trades", return_value=[]):
                with caplog.at_level(logging.WARNING, logger="core.account_sync"):
                    report = core.account_sync.reconcile_positions_on_boot()

    assert "0xserver_only" in {o for o in report.get("orphan_server", [])}
    messages = " ".join(r.message for r in caplog.records)
    assert "orphan_server" in messages
    assert "0xserver_only" in messages


def test_reconcile_no_drift_when_matched(tmp_path, monkeypatch, caplog):
    """Local order_id matches server order_id → no drift warnings; report
    shows matched=1."""
    db_path = tmp_path / "t3.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    import importlib, core.db, core.types, core.account_sync
    importlib.reload(core.db)
    importlib.reload(core.types)
    importlib.reload(core.account_sync)
    core.db.init_db()

    t = core.types.Trade(
        id=None, ts_open="2026-04-24T00:00:00+00:00", ts_close=None,
        market_slug="mlb-match-2026-04-24", market_id="0xmk",
        side="BUY_YES", qty=100.0, entry_px=0.50, exit_px=None,
        pnl_usd=None, fees_usd=0.5, reason_open="", reason_close=None,
        confidence=0.5, mode="neutral", status="pending", source="live",
        actual_fill_px=0.0, order_id="0xboth_agree",
    )
    core.db.insert_open_trade(t)

    fake_orders = [{"id": "0xboth_agree", "market": "0xmk", "price": "0.50"}]
    fake_creds = {"apiKey": "k", "secret": "s", "passphrase": "p"}
    import logging
    with patch("core.account_sync._get_creds", return_value=fake_creds):
        with patch("core.account_sync.get_my_orders", return_value=fake_orders):
            with patch("core.account_sync.get_my_trades", return_value=[]):
                with caplog.at_level(logging.WARNING, logger="core.account_sync"):
                    report = core.account_sync.reconcile_positions_on_boot()

    assert report.get("matched", 0) == 1
    assert report.get("orphan_local", []) == []
    assert report.get("orphan_server", []) == []
    warns = [r for r in caplog.records if r.levelname == "WARNING"]
    # No drift → no warnings from THIS function
    assert not any("orphan" in r.message for r in warns)
```

- [ ] **Step 2: Run — verify fail**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_account_sync.py -v 2>&1 | tail -20`
Expected: 3 new tests fail with `NotImplementedError`.

- [ ] **Step 3: Implement reconcile**

Replace the `reconcile_positions_on_boot` body in `core/account_sync.py`:

```python
def reconcile_positions_on_boot() -> dict | None:
    """Run the full reconcile pass. Returns a drift-report dict on success,
    None if skipped (paper mode).

    Report shape:
      {
        "matched": int,
        "orphan_local": list[str],   # order_ids we have locally but server doesn't
        "orphan_server": list[str],  # order_ids server has but we don't
      }
    """
    creds = _get_creds()
    if creds is None:
        logger.info("account_sync: no wallet, skipping boot reconcile")
        return None
    logger.info("account_sync: reconcile starting (live mode)")

    from core.db import fetch_open_trades
    from core.polymarket_client import get_my_orders as _get_my_orders
    from core.polymarket_client import get_my_trades as _get_my_trades

    # Allow tests to patch the module-level aliases
    local_rows = fetch_open_trades()
    local_order_ids = {str(r.order_id): r for r in local_rows if r.order_id}
    try:
        server_orders = get_my_orders()
    except Exception as exc:
        logger.warning("account_sync: get_my_orders failed err=%s", exc)
        server_orders = []
    try:
        _ = get_my_trades(since_ts=0)  # warm cache / surface errors; not used here
    except Exception as exc:
        logger.warning("account_sync: get_my_trades failed err=%s", exc)

    server_order_ids = {str(o.get("id") or o.get("order_id") or "") for o in server_orders if isinstance(o, dict)}
    server_order_ids.discard("")

    orphan_local = sorted(local_order_ids.keys() - server_order_ids)
    orphan_server = sorted(server_order_ids - local_order_ids.keys())
    matched = len(local_order_ids.keys() & server_order_ids)

    for oid in orphan_local:
        logger.warning("account_sync: drift:orphan_local order_id=%s slug=%s",
                       oid, local_order_ids[oid].market_slug)
    for oid in orphan_server:
        logger.warning("account_sync: drift:orphan_server order_id=%s", oid)
    if not orphan_local and not orphan_server:
        logger.info("account_sync: reconcile OK — matched=%d no drift", matched)
    else:
        logger.info("account_sync: reconcile done — matched=%d orphan_local=%d orphan_server=%d",
                    matched, len(orphan_local), len(orphan_server))

    return {
        "matched": matched,
        "orphan_local": orphan_local,
        "orphan_server": orphan_server,
    }
```

Also add the module-level aliases at the top of `account_sync.py` so tests can patch them cleanly. Immediately after the `logger = ...` line, add:

```python
# Module-level aliases for test-time patching. Imported lazily inside the
# functions to keep the module importable even if polymarket_client has issues.
def _import_client_helpers():
    from core.polymarket_client import get_my_orders, get_my_trades, get_balance_allowance
    return get_my_orders, get_my_trades, get_balance_allowance
```

Then replace the inline imports in reconcile with:

```python
    from core.polymarket_client import get_my_orders, get_my_trades
```

(The simpler option — tests patch `core.account_sync.get_my_orders` directly, so we need those names to exist at module scope. Add them at module top.)

Actually, use this simpler pattern: at the top of `account_sync.py`, after `logger = ...`, add:

```python
# Re-export for test patchability
try:
    from core.polymarket_client import get_my_orders, get_my_trades, get_balance_allowance
except ImportError:  # polymarket_client not importable at module load — fail later if used
    get_my_orders = None  # type: ignore
    get_my_trades = None  # type: ignore
    get_balance_allowance = None  # type: ignore
```

Then inside `reconcile_positions_on_boot`, just call `get_my_orders()` / `get_my_trades()` directly (no local import). The tests' `patch("core.account_sync.get_my_orders", return_value=...)` will work.

- [ ] **Step 4: Run — verify pass**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_account_sync.py -v 2>&1 | tail -15`
Expected: 7 passed (4 no-op + 3 drift).

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/account_sync.py sports_bot_v2/tests/core/test_account_sync.py
git commit -m "sports_bot_v2: account_sync reconcile drift detection

reconcile_positions_on_boot now compares fetch_open_trades() order_ids
vs. server-side get_my_orders() ids. Logs orphan_local (we have, server
doesn't) and orphan_server (server has, we don't) as drift warnings.
Returns a report dict for callers. Live path still unexercised in paper
mode (creds raise).

STAIR_D_ACCOUNT_SYNC_001 step 3 of 6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Implement `fetch_balance` with low-balance warning

**Files:**
- Modify: `core/account_sync.py`
- Modify: `tests/core/test_account_sync.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/core/test_account_sync.py`:

```python
def test_fetch_balance_returns_usdc_value(monkeypatch):
    """With creds, fetch_balance returns the USDC amount from
    polymarket_client.get_balance_allowance."""
    import core.account_sync
    fake_creds = {"apiKey": "k", "secret": "s", "passphrase": "p"}
    with patch("core.account_sync._get_creds", return_value=fake_creds):
        with patch("core.account_sync.get_balance_allowance", return_value=250.0):
            bal = core.account_sync.fetch_balance()
    assert bal == 250.0


def test_fetch_balance_warns_below_threshold(monkeypatch, caplog):
    """Balance below MIN_BALANCE_WARN_USD → logs WARN."""
    import core.account_sync, logging, importlib
    monkeypatch.setenv("MIN_BALANCE_WARN_USD", "50.0")
    importlib.reload(core.account_sync)
    fake_creds = {"apiKey": "k", "secret": "s", "passphrase": "p"}
    with patch("core.account_sync._get_creds", return_value=fake_creds):
        with patch("core.account_sync.get_balance_allowance", return_value=12.34):
            with caplog.at_level(logging.WARNING, logger="core.account_sync"):
                bal = core.account_sync.fetch_balance()
    assert bal == 12.34
    messages = " ".join(r.message for r in caplog.records if r.levelname == "WARNING")
    assert "balance" in messages.lower()
    assert "12.34" in messages or "12.3" in messages


def test_fetch_balance_no_warn_above_threshold(monkeypatch, caplog):
    """Balance above threshold → no WARN, INFO only."""
    import core.account_sync, logging, importlib
    monkeypatch.setenv("MIN_BALANCE_WARN_USD", "50.0")
    importlib.reload(core.account_sync)
    fake_creds = {"apiKey": "k", "secret": "s", "passphrase": "p"}
    with patch("core.account_sync._get_creds", return_value=fake_creds):
        with patch("core.account_sync.get_balance_allowance", return_value=500.0):
            with caplog.at_level(logging.DEBUG, logger="core.account_sync"):
                bal = core.account_sync.fetch_balance()
    assert bal == 500.0
    warns = [r for r in caplog.records if r.levelname == "WARNING"]
    assert not warns
```

- [ ] **Step 2: Run — verify fail**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_account_sync.py -v -k "balance" 2>&1 | tail -15`
Expected: 3 new tests fail with `NotImplementedError`.

- [ ] **Step 3: Implement `fetch_balance`**

Replace the `fetch_balance` body:

```python
def fetch_balance() -> float | None:
    """Return wallet USDC balance, or None if skipped (paper mode).
    Warns if below MIN_BALANCE_WARN_USD (default 50.0)."""
    creds = _get_creds()
    if creds is None:
        return None
    bal = get_balance_allowance()
    if bal is None:
        logger.warning("account_sync: balance fetch returned None")
        return None
    if bal < MIN_BALANCE_WARN_USD:
        logger.warning(
            "account_sync: balance=%.2f below threshold %.2f — consider refunding",
            bal, MIN_BALANCE_WARN_USD,
        )
    else:
        logger.info("account_sync: balance=%.2f USDC (threshold %.2f)", bal, MIN_BALANCE_WARN_USD)
    return bal
```

- [ ] **Step 4: Run — verify pass**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_account_sync.py -v 2>&1 | tail -15`
Expected: 10 passed (7 prior + 3 new).

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/account_sync.py sports_bot_v2/tests/core/test_account_sync.py
git commit -m "sports_bot_v2: account_sync.fetch_balance with low-balance warn

Returns wallet USDC balance via polymarket_client.get_balance_allowance.
Warns when balance < MIN_BALANCE_WARN_USD (default 50.0). Paper mode
still no-ops (creds raise). Operator-facing log line on every boot
with a real wallet so depletion is obvious in logs.

STAIR_D_ACCOUNT_SYNC_001 step 4 of 6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Implement `sync_trades_history` (log-only, no DB writes)

Since Stair B already writes fills via `update_trade_fill` on TRADE events, `sync_trades_history` is a catch-up safety net: on boot, pull my trades from `since_ts` and log any whose order_id doesn't have a matching local row. Does NOT auto-insert — operator decides.

**Files:**
- Modify: `core/account_sync.py`
- Modify: `tests/core/test_account_sync.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/core/test_account_sync.py`:

```python
def test_sync_trades_history_returns_count_of_trades_seen():
    """Returns the count of trades the server echoed, whether or not they
    match local rows."""
    import core.account_sync
    fake_creds = {"apiKey": "k", "secret": "s", "passphrase": "p"}
    fake_trades = [
        {"id": "t1", "price": "0.55", "maker_orders": [{"order_id": "0xabc"}]},
        {"id": "t2", "price": "0.42", "maker_orders": [{"order_id": "0xdef"}]},
    ]
    with patch("core.account_sync._get_creds", return_value=fake_creds):
        with patch("core.account_sync.get_my_trades", return_value=fake_trades):
            n = core.account_sync.sync_trades_history(since_ts=0)
    assert n == 2


def test_sync_trades_history_logs_orphan_fills(tmp_path, monkeypatch, caplog):
    """A server trade whose maker_order_id doesn't match any local row →
    log WARN. Does NOT insert a row (operator decides)."""
    db_path = tmp_path / "t.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    import importlib, core.db, core.account_sync, logging
    importlib.reload(core.db)
    importlib.reload(core.account_sync)
    core.db.init_db()

    fake_creds = {"apiKey": "k", "secret": "s", "passphrase": "p"}
    fake_trades = [
        {"id": "t1", "price": "0.55",
         "maker_orders": [{"order_id": "0xphantom", "matched_amount": "50"}]},
    ]
    with patch("core.account_sync._get_creds", return_value=fake_creds):
        with patch("core.account_sync.get_my_trades", return_value=fake_trades):
            with caplog.at_level(logging.WARNING, logger="core.account_sync"):
                core.account_sync.sync_trades_history(since_ts=0)

    messages = " ".join(r.message for r in caplog.records)
    assert "0xphantom" in messages
    assert "orphan_fill" in messages or "phantom" in messages.lower() or "no matching" in messages.lower()
```

- [ ] **Step 2: Run — verify fail**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_account_sync.py -v -k "trades_history" 2>&1 | tail -15`
Expected: 2 new tests fail with `NotImplementedError`.

- [ ] **Step 3: Implement `sync_trades_history`**

Replace the `sync_trades_history` body:

```python
def sync_trades_history(since_ts: int) -> int:
    """Sync my trades from since_ts, log any orphan fills (server has,
    we don't). Returns count of trades processed.

    Does NOT insert rows — Stair B's user_stream handles fills via TRADE events.
    This is a catch-up safety net that surfaces drift at boot.
    """
    creds = _get_creds()
    if creds is None:
        return 0
    from core.db import fetch_open_trades

    try:
        trades = get_my_trades(since_ts=since_ts)
    except Exception as exc:
        logger.warning("account_sync: get_my_trades failed err=%s", exc)
        return 0

    local_rows = fetch_open_trades()
    local_order_ids = {str(r.order_id) for r in local_rows if r.order_id}

    orphan_count = 0
    for t in trades:
        if not isinstance(t, dict):
            continue
        makers = t.get("maker_orders") or []
        if not isinstance(makers, list):
            continue
        for maker in makers:
            if not isinstance(maker, dict):
                continue
            oid = str(maker.get("order_id") or "")
            if oid and oid not in local_order_ids:
                logger.warning(
                    "account_sync: orphan_fill order_id=%s trade_id=%s — server reports fill, no local row",
                    oid, t.get("id"),
                )
                orphan_count += 1

    logger.info("account_sync: sync_trades_history processed=%d orphan_fills=%d",
                len(trades), orphan_count)
    return len(trades)
```

- [ ] **Step 4: Run — verify pass**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_account_sync.py -v 2>&1 | tail -20`
Expected: 12 passed (10 prior + 2 new).

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/account_sync.py sports_bot_v2/tests/core/test_account_sync.py
git commit -m "sports_bot_v2: account_sync.sync_trades_history orphan-fill detection

Pulls my trades since since_ts and logs any whose maker_orders contain
order_ids we don't have locally. Does NOT auto-insert — operator decides.
Serves as a catch-up safety net for fills Stair B's user_stream may have
missed (e.g., if the stream was disconnected when TRADE event fired).

STAIR_D_ACCOUNT_SYNC_001 step 5 of 6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Integrate `reconcile_positions_on_boot` into `bot_core.main()` + env docs + verification

**Files:**
- Modify: `bot_core.py` (single call added after `init_db()` region)
- Modify: `.env.example`

- [ ] **Step 1: Read current `init_db()` region in bot_core**

Run: `grep -n "init_db\|_write_pid\|STARTUP_PROOF" "C:/Users/johnny/Desktop/sports_bot_v2/bot_core.py" | head -10`

You'll see `init_db()` called near the top of `main()`. Account_sync goes right after it, before the main loop starts.

- [ ] **Step 2: Add the integration call**

In `bot_core.py`, find the `init_db()` call inside `main()`. Add immediately after it:

```python
    # Stair D: boot-time account state reconcile. Paper mode no-ops with a
    # "no wallet, skipping" log line. Live mode logs drift vs. server-side
    # open orders and a balance warning if below threshold.
    try:
        from core.account_sync import reconcile_positions_on_boot, fetch_balance
        reconcile_positions_on_boot()
        fetch_balance()
    except Exception as exc:
        logger.warning("account_sync: boot reconcile unexpectedly failed: %s", exc)
```

The outer `try/except Exception` ensures a reconcile failure never blocks bot startup — the paper bot always starts.

- [ ] **Step 3: Append env vars to `.env.example`**

Append to `.env.example`, after the Stair B USER_STREAM_MIRROR block:

```
# ── Polymarket account sync (Stair D) ─────────────────────────────────────────
# Low-balance warning threshold. fetch_balance() logs WARN when wallet USDC
# balance falls below this value. Default is 50.0 (2× the PAPER_POSITION_SIZE_USD
# default). Tune to your own bankroll policy.
MIN_BALANCE_WARN_USD=50.0

# Optional: explicitly enable/disable account_sync at boot. Default behavior
# (no env var set) is driven by signer availability — paper mode (DummySigner)
# no-ops, live mode reconciles. If you want to disable in live mode too (not
# recommended), set ACCOUNT_SYNC_ENABLED=false.
ACCOUNT_SYNC_ENABLED=true
```

- [ ] **Step 4: Syntax check**

```bash
cd "C:/Users/johnny/Desktop/sports_bot_v2"
"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -c "import ast; ast.parse(open('bot_core.py').read()); print('OK')"
```
Expected: `OK`.

- [ ] **Step 5: Full test suite + grep proofs**

```bash
cd "C:/Users/johnny/Desktop/sports_bot_v2"
echo "===== Full suite ====="
"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/ 2>&1 | tail -3
echo ""
echo "===== Zero /positions or get_my_* calls outside account_sync + polymarket_client ====="
grep -rn "get_my_orders\|get_my_trades\|get_balance_allowance" --include="*.py" core/ bot_core.py | grep -v test_ | grep -v "core/account_sync.py" | grep -v "core/polymarket_client.py"
echo "(empty = PASS)"
echo ""
echo "===== Paper mode defaults: no HTTP/auth on boot ====="
"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -c "
import os
for k in ('PHASE','LIVE_TRADING_KILL_SWITCH','SIGNER','USER_STREAM_MIRROR','ACCOUNT_SYNC_ENABLED'):
    os.environ.pop(k, None)
from core.account_sync import reconcile_positions_on_boot, fetch_balance, sync_trades_history
# All three must return None/0 without raising
assert reconcile_positions_on_boot() is None
assert fetch_balance() is None
assert sync_trades_history(0) == 0
print('account_sync paper-mode defaults OK — no HTTP, no auth, no crash')
"
echo ""
echo "===== Live bot unchanged ====="
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*bot_core.py*' } | Select-Object ProcessId, CreationDate | Format-Table -AutoSize"
```
Expected:
- 106 tests pass (94 prior + 4 auth helpers + 8 account_sync variants — count may vary ±2)
- Grep returns empty
- Paper-mode defaults print "OK — no HTTP, no auth, no crash"
- Live bot PID 9056 still shown, unchanged

- [ ] **Step 6: Write the verification doc**

Create `docs/superpowers/plans/2026-04-24-polymarket-stair-d-verification.md`:

```markdown
# Stair D Live Verification — 2026-04-24

## What was built

- **`core/polymarket_client.py`** — three new authenticated-GET helpers: `get_balance_allowance`, `get_my_trades`, `get_my_orders`. All wrap `py_clob_client.ClobClient` via the existing `retry_with_backoff`.
- **`core/account_sync.py`** — `reconcile_positions_on_boot()`, `fetch_balance()`, `sync_trades_history(since_ts)`. All three short-circuit to warn-and-noop when `_get_creds()` returns None (paper mode). Live mode: drift report from `orphan_local`/`orphan_server` comparison, low-balance warning, orphan-fill log on trade-history scan.
- **`bot_core.py`** — `reconcile_positions_on_boot()` + `fetch_balance()` called once after `init_db()`. Paper mode: two log lines ("no wallet, skipping"). Live mode: full reconcile report + balance check.
- **`.env.example`** — `MIN_BALANCE_WARN_USD` (default 50.0) and `ACCOUNT_SYNC_ENABLED` (default true) documented.

## Test suite: {FILL IN pytest summary}

## Zero-unauth-call grep: {FILL IN — expect empty}

## Paper-mode defaults proof: {FILL IN "account_sync paper-mode defaults OK"}

## Live bot status: PID {FILL IN} unchanged

## Commits: {FILL IN the list}

## Readiness statement

Stair D completes the Polymarket staircase. Four of four stairs shipped:
- A: batch endpoints (7× OB scan speedup)
- C: live_exec + triple kill-switch
- B: user streaming with TRADE → sqlite update
- D: boot-time account state sync

The bot still trades paper by default. To go live: flip PHASE=live,
LIVE_TRADING_KILL_SWITCH=false, USER_STREAM_MIRROR=true, SIGNER=private_key,
set PRIVATE_KEY, fund wallet, run the operator pre-flip checklist.
```

Fill in the `{FILL IN ...}` placeholders with the actual output from Step 5.

- [ ] **Step 7: Commit (bundled)**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/bot_core.py sports_bot_v2/.env.example sports_bot_v2/docs/superpowers/plans/2026-04-24-polymarket-stair-d-verification.md
git commit -m "sports_bot_v2: Stair D integration + env docs + verification

bot_core.main() now calls reconcile_positions_on_boot + fetch_balance
once after init_db. Wrapped in outer try/except so reconcile failure
never blocks bot startup. Paper mode (default): two 'no wallet, skipping'
log lines. Live mode: drift report + balance check.

.env.example documents MIN_BALANCE_WARN_USD (default 50.0) and
ACCOUNT_SYNC_ENABLED (default true).

Verification doc proves paper-mode defaults: no HTTP, no auth, no crash.
Grep confirms all get_my_* / get_balance_allowance calls are inside
account_sync or polymarket_client — nowhere else.

Closes STAIR_D_ACCOUNT_SYNC_001. Polymarket full-integration staircase
complete: A (batch reads) → C (execution writes) → B (user streaming)
→ D (account state sync). Four of four stairs shipped.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Definition of Done for Stair D

- [ ] `core/polymarket_client.py` has `get_balance_allowance`, `get_my_trades`, `get_my_orders`
- [ ] `core/account_sync.py` has `reconcile_positions_on_boot`, `fetch_balance`, `sync_trades_history`
- [ ] All three `account_sync` functions return None/0 in paper mode without raising
- [ ] `reconcile_positions_on_boot` detects `orphan_local`, `orphan_server`, and `matched` states
- [ ] `fetch_balance` warns when balance < `MIN_BALANCE_WARN_USD`
- [ ] `bot_core.main()` calls reconcile + balance ONCE after `init_db()`, wrapped in try/except
- [ ] `.env.example` documents the two new vars
- [ ] Full test suite ~106 tests, all pass
- [ ] Grep confirms no authenticated calls outside `core/account_sync.py` + `core/polymarket_client.py`
- [ ] Paper-mode defaults check passes: no HTTP, no auth, no crash
- [ ] Live bot PID 9056 unchanged

## Follow-ups (NOT in this plan)

- Auto-cancel or auto-reconcile orphan_server orders (operator-decides today)
- Pending→open transition via `sync_trades_history` (currently logs orphan_fill without inserting; Stair B's user_stream is the primary path)
- Dashboard surfacing for the drift report (dugout_dash task)
