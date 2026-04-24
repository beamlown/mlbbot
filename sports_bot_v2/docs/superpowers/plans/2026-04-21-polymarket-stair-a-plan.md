# Polymarket Stair A (A-Slim) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a typed Polymarket CLOB facade (`core/polymarket_client.py`) that exposes batch `midpoints`/`prices`/`spreads`, single `last_trade_price`/`tick_size`, with a disk-persisted tick-size cache and 429-`Retry-After`-aware retry — then wire it into bot_core's per-loop scan behind a `USE_BATCH_PRICES` feature flag so we can swap 180 parallel `/book` GETs for a single batched call.

**Architecture:** Thin wrapper around the already-installed `py_clob_client 0.34.6`. The SDK handles URL routing, JSON parsing, and its own in-memory tick-size cache; we add on top: typed return shapes, disk persistence for tick sizes across restarts, and transparent 429 backoff that reads the server's `Retry-After` hint.

**Tech Stack:** Python 3.14, `py_clob_client 0.34.6`, `pytest 9.0.2`, `unittest.mock`, `websocket-client` (already in use elsewhere).

**Spec reference:** `docs/superpowers/specs/2026-04-20-polymarket-integration-design.md` (Stair A section)

**Work-order alias:** `STAIR_A_BATCH_ENDPOINTS_001`

---

## File Structure

| File | Role | New/Modify |
|---|---|---|
| `core/polymarket_client.py` | Typed facade over py_clob_client; batch endpoints; tick-size disk cache | **NEW** |
| `tests/core/test_polymarket_client.py` | Unit tests for all facade methods (mocked ClobClient) | **NEW** |
| `tests/core/test_utils_retry.py` | Unit tests for 429-Retry-After extension | **NEW** |
| `core/utils.py` (lines 60–80) | Extend `retry_with_backoff` to honor `Retry-After`; add `RateLimitError` helper | MODIFY |
| `bot_core.py` (line 501 region) | Add `USE_BATCH_PRICES` branch that calls `polymarket_client.batch_midpoints`+`batch_prices` before the OB walk | MODIFY |
| `bot_core.py` (discovery section, ~line 430/465) | Call `polymarket_client.refresh_tick_sizes(tokens)` after each discovery | MODIFY |
| `.env.example` | Document `USE_BATCH_PRICES`, `TICK_SIZE_CACHE_PATH`, `CLOB_HOST` | MODIFY |
| `runtime/tick_sizes.json` | Disk cache artifact (gitignored via existing `runtime/` ignore pattern) | **NEW** (written at runtime) |
| `requirements.txt` | Pin `py_clob_client>=0.34,<0.35` so tests don't silently depend on globally-installed version | MODIFY |

**Decomposition rationale:** `polymarket_client.py` is the single new module so every Stair in the staircase (A/C/B/D) can route all Polymarket HTTP through one place. `retry_with_backoff` stays in `core/utils.py` because it's used by discovery/orderbook/live_stats/etc.; extending in-place avoids a second retry helper.

---

## Task 1: Confirm environment and test harness

**Files:**
- Read only: `core/utils.py`, `core/discovery.py`, `tests/`, `requirements.txt`

- [ ] **Step 1: Verify pytest works**

Run: `cd C:/Users/johnny/Desktop/sports_bot_v2 && "C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest --collect-only -q 2>&1 | tail -20`
Expected: pytest enumerates zero-or-more tests without error. If it errors on imports, fix before proceeding.

- [ ] **Step 2: Verify py_clob_client importable**

Run:
```bash
"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -c "from py_clob_client.client import ClobClient; from py_clob_client.clob_types import BookParams; print('OK')"
```
Expected: prints `OK`. If it fails with ImportError, run `python -m pip install py_clob_client==0.34.6`.

- [ ] **Step 3: Read `core/utils.py` lines 55–95**

Open the file; find `is_transient_error` and `retry_with_backoff`. Note that `is_transient_error` already treats `HTTPError.code == 429` as transient but the retry uses fixed exponential backoff — it ignores the server's `Retry-After` header.

No commit in this task.

---

## Task 2: Extend `retry_with_backoff` to honor HTTP 429 `Retry-After`

**Files:**
- Modify: `core/utils.py` (around lines 60–80)
- Create: `tests/core/__init__.py` (empty)
- Create: `tests/core/test_utils_retry.py`

- [ ] **Step 1: Create empty test package marker**

Create file `tests/core/__init__.py` with no content.

```bash
New-Item -ItemType File -Path tests/core/__init__.py -Force
```

(Powershell; bash equivalent: `mkdir -p tests/core && : > tests/core/__init__.py`)

- [ ] **Step 2: Write the failing test**

Create `tests/core/test_utils_retry.py`:

```python
"""Tests for core.utils.retry_with_backoff — 429 Retry-After honoring."""
from __future__ import annotations

import time
from email.message import Message
from urllib.error import HTTPError

import pytest

from core.utils import retry_with_backoff


def _make_429(retry_after: str | None) -> HTTPError:
    hdrs = Message()
    if retry_after is not None:
        hdrs["Retry-After"] = retry_after
    return HTTPError(url="http://x", code=429, msg="Too Many Requests", hdrs=hdrs, fp=None)


def test_honors_retry_after_seconds(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 2:
            raise _make_429("2")
        return "ok"

    result = retry_with_backoff(fn, retries=3, backoff_ms=500)

    assert result == "ok"
    assert calls["n"] == 2
    # First sleep must be >= 2s (server's hint), not the 0.5s default first backoff
    assert slept and slept[0] >= 2.0


def test_falls_back_to_exponential_when_no_retry_after(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 2:
            raise _make_429(None)
        return "ok"

    result = retry_with_backoff(fn, retries=3, backoff_ms=500)

    assert result == "ok"
    # Without Retry-After we fall back to ~0.5s base backoff
    assert slept and slept[0] < 2.0


def test_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: None)

    def fn():
        raise _make_429("1")

    with pytest.raises(HTTPError):
        retry_with_backoff(fn, retries=2, backoff_ms=100)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_utils_retry.py -v 2>&1 | tail -20`
Expected: `test_honors_retry_after_seconds` FAILS — first `slept[0]` will be ~0.5s (current implementation ignores Retry-After), not ≥2.0s. Other two may pass already.

- [ ] **Step 4: Implement the change in `core/utils.py`**

Open `core/utils.py`, replace the existing `retry_with_backoff` function with:

```python
def _retry_after_seconds(exc: Exception) -> float | None:
    """If exc is an HTTPError carrying a Retry-After header, return seconds to wait.
    Accepts numeric seconds; HTTP-date Retry-After values are ignored (rare in practice)."""
    if not isinstance(exc, urllib.error.HTTPError):
        return None
    try:
        raw = exc.headers.get("Retry-After") if exc.headers else None
    except Exception:
        raw = None
    if not raw:
        return None
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return None


def retry_with_backoff(fn: Callable, retries: int = 3, backoff_ms: int = 500) -> Any:
    """Exponential backoff + jitter on transient errors.

    If the server returns HTTP 429 with a numeric `Retry-After` header, sleep for
    that many seconds instead of the computed backoff.
    """
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:
            if attempt >= retries or not is_transient_error(exc):
                raise
            hinted = _retry_after_seconds(exc)
            if hinted is not None and hinted > 0:
                sleep_s = hinted
            else:
                sleep_ms = backoff_ms * (2 ** attempt) + random.randint(0, max(50, backoff_ms // 3))
                sleep_s = sleep_ms / 1000.0
            time.sleep(sleep_s)
            attempt += 1
```

- [ ] **Step 5: Run test to verify it passes**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_utils_retry.py -v 2>&1 | tail -20`
Expected: all three tests PASS.

- [ ] **Step 6: Verify no other callers broke**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -c "from core.utils import retry_with_backoff, is_transient_error, _retry_after_seconds; print('imports ok')"`
Expected: `imports ok`.

- [ ] **Step 7: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/utils.py sports_bot_v2/tests/core/__init__.py sports_bot_v2/tests/core/test_utils_retry.py
git commit -m "sports_bot_v2: retry_with_backoff honors HTTP 429 Retry-After header

Adds a _retry_after_seconds helper that extracts numeric Retry-After from
HTTPError.headers; retry_with_backoff sleeps for that duration instead of
the computed exponential backoff when present. Covered by three tests.

STAIR_A_BATCH_ENDPOINTS_001 prep.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Scaffold `core/polymarket_client.py` + module smoke test

**Files:**
- Create: `core/polymarket_client.py`
- Create: `tests/core/test_polymarket_client.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_polymarket_client.py`:

```python
"""Tests for core.polymarket_client facade."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_module_importable():
    import core.polymarket_client as pm
    assert hasattr(pm, "batch_midpoints")
    assert hasattr(pm, "batch_prices")
    assert hasattr(pm, "batch_spreads")
    assert hasattr(pm, "last_trade_price")
    assert hasattr(pm, "tick_size")
    assert hasattr(pm, "refresh_tick_sizes")


def test_get_client_memoizes():
    import core.polymarket_client as pm
    # Force a fresh client for this test
    pm._client = None
    with patch("core.polymarket_client.ClobClient") as MockClob:
        MockClob.return_value = MagicMock()
        c1 = pm._get_client()
        c2 = pm._get_client()
    assert c1 is c2
    assert MockClob.call_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_polymarket_client.py -v 2>&1 | tail -20`
Expected: both tests FAIL — `ModuleNotFoundError: No module named 'core.polymarket_client'`.

- [ ] **Step 3: Create the module**

Create `core/polymarket_client.py`:

```python
"""
core/polymarket_client.py — Typed facade over the Polymarket CLOB.

This module is the single route for all Polymarket HTTP traffic. It wraps
py_clob_client with:
  - typed return shapes (dict[token_id, float] instead of dict[token_id, str])
  - 429 Retry-After-aware retries via core.utils.retry_with_backoff
  - disk-persisted tick-size cache surviving process restarts

Unauthenticated endpoints only (midpoints/prices/spreads/last_trade_price/tick_size).
Authenticated endpoints (place_order, cancel_order) come with Stair C.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BookParams

from core.utils import retry_with_backoff

logger = logging.getLogger("core.polymarket_client")

CLOB_HOST = os.getenv("CLOB_HOST", "https://clob.polymarket.com")
POLYGON_CHAIN_ID = int(os.getenv("POLYGON_CHAIN_ID", "137"))
TICK_SIZE_CACHE_PATH = Path(os.getenv("TICK_SIZE_CACHE_PATH", "runtime/tick_sizes.json"))
RETRIES = int(os.getenv("POLYMARKET_CLIENT_RETRIES", "3"))
BACKOFF_MS = int(os.getenv("POLYMARKET_CLIENT_BACKOFF_MS", "500"))

_client: ClobClient | None = None
_tick_cache: dict[str, float] = {}
_tick_cache_loaded: bool = False


def _get_client() -> ClobClient:
    global _client
    if _client is None:
        _client = ClobClient(host=CLOB_HOST, chain_id=POLYGON_CHAIN_ID)
    return _client


def _load_tick_cache() -> None:
    global _tick_cache, _tick_cache_loaded
    if _tick_cache_loaded:
        return
    _tick_cache_loaded = True
    if not TICK_SIZE_CACHE_PATH.exists():
        return
    try:
        raw = json.loads(TICK_SIZE_CACHE_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            _tick_cache = {str(k): float(v) for k, v in raw.items()}
        logger.info("tick_size cache loaded n=%d path=%s", len(_tick_cache), TICK_SIZE_CACHE_PATH)
    except Exception as exc:
        logger.warning("tick_size cache load failed path=%s err=%s", TICK_SIZE_CACHE_PATH, exc)
        _tick_cache = {}


def _save_tick_cache() -> None:
    try:
        TICK_SIZE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        TICK_SIZE_CACHE_PATH.write_text(json.dumps(_tick_cache, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("tick_size cache save failed path=%s err=%s", TICK_SIZE_CACHE_PATH, exc)


# --- batch endpoints (stubs — filled in by subsequent tasks) ------------------
def batch_midpoints(token_ids: list[str]) -> dict[str, float]:
    raise NotImplementedError

def batch_prices(token_ids: list[str], side: str = "SELL") -> dict[str, float]:
    raise NotImplementedError

def batch_spreads(token_ids: list[str]) -> dict[str, float]:
    raise NotImplementedError

def last_trade_price(token_id: str) -> tuple[float, int] | None:
    raise NotImplementedError

def tick_size(token_id: str) -> float:
    raise NotImplementedError

def refresh_tick_sizes(token_ids: list[str]) -> int:
    raise NotImplementedError
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_polymarket_client.py -v 2>&1 | tail -20`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/polymarket_client.py sports_bot_v2/tests/core/test_polymarket_client.py
git commit -m "sports_bot_v2: scaffold core/polymarket_client.py facade

Adds module skeleton with _get_client (memoized ClobClient) and tick-cache
load/save helpers. All public methods are NotImplementedError stubs that
subsequent tasks will fill in one at a time.

STAIR_A_BATCH_ENDPOINTS_001 step 1 of 6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Implement `batch_midpoints`

**Files:**
- Modify: `core/polymarket_client.py` (`batch_midpoints` stub)
- Modify: `tests/core/test_polymarket_client.py`

- [ ] **Step 1: Append the failing test**

Append to `tests/core/test_polymarket_client.py`:

```python
def test_batch_midpoints_empty_returns_empty():
    import core.polymarket_client as pm
    assert pm.batch_midpoints([]) == {}


def test_batch_midpoints_calls_sdk_and_casts_to_float():
    import core.polymarket_client as pm
    pm._client = None
    fake_client = MagicMock()
    fake_client.get_midpoints.return_value = {"tok_a": "0.55", "tok_b": "0.42"}
    with patch("core.polymarket_client._get_client", return_value=fake_client):
        out = pm.batch_midpoints(["tok_a", "tok_b"])
    assert out == {"tok_a": 0.55, "tok_b": 0.42}
    # SDK was called with a list of BookParams
    args, kwargs = fake_client.get_midpoints.call_args
    params = args[0] if args else kwargs.get("params")
    assert len(params) == 2
    assert all(p.token_id in {"tok_a", "tok_b"} for p in params)


def test_batch_midpoints_handles_missing_tokens_gracefully():
    """SDK may not echo all requested tokens back (unknown market). We only
    return what we got."""
    import core.polymarket_client as pm
    pm._client = None
    fake_client = MagicMock()
    fake_client.get_midpoints.return_value = {"tok_a": "0.55"}
    with patch("core.polymarket_client._get_client", return_value=fake_client):
        out = pm.batch_midpoints(["tok_a", "tok_b"])
    assert out == {"tok_a": 0.55}
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_polymarket_client.py -v -k "midpoints" 2>&1 | tail -20`
Expected: all three midpoints tests FAIL with `NotImplementedError`.

- [ ] **Step 3: Replace the `batch_midpoints` stub**

In `core/polymarket_client.py`, replace the stub with:

```python
def batch_midpoints(token_ids: list[str]) -> dict[str, float]:
    """Fetch midpoint (bid+ask)/2 for each token. Returns {token_id: mid_float}.

    Tokens not known to the CLOB are silently omitted from the result.
    """
    if not token_ids:
        return {}
    client = _get_client()
    params = [BookParams(token_id=tid) for tid in token_ids]
    resp = retry_with_backoff(
        lambda: client.get_midpoints(params=params),
        retries=RETRIES, backoff_ms=BACKOFF_MS,
    )
    out: dict[str, float] = {}
    if isinstance(resp, dict):
        for tid, mid in resp.items():
            try:
                out[str(tid)] = float(mid)
            except (TypeError, ValueError):
                logger.warning("batch_midpoints: unparseable mid token=%s val=%r", tid, mid)
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_polymarket_client.py -v -k "midpoints" 2>&1 | tail -20`
Expected: three midpoints tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/polymarket_client.py sports_bot_v2/tests/core/test_polymarket_client.py
git commit -m "sports_bot_v2: polymarket_client.batch_midpoints

Wraps ClobClient.get_midpoints; casts decimal-string values to float;
silently omits tokens the CLOB didn't recognize. Retries via our
429-aware retry_with_backoff.

STAIR_A_BATCH_ENDPOINTS_001 step 2 of 6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Implement `batch_prices`

**Files:**
- Modify: `core/polymarket_client.py` (`batch_prices` stub)
- Modify: `tests/core/test_polymarket_client.py`

- [ ] **Step 1: Append the failing test**

Append to `tests/core/test_polymarket_client.py`:

```python
def test_batch_prices_passes_side_and_casts():
    import core.polymarket_client as pm
    pm._client = None
    fake_client = MagicMock()
    fake_client.get_prices.return_value = {"tok_a": {"BUY": "0.50", "SELL": "0.54"}}
    with patch("core.polymarket_client._get_client", return_value=fake_client):
        out = pm.batch_prices(["tok_a"], side="SELL")
    assert out == {"tok_a": 0.54}
    args, kwargs = fake_client.get_prices.call_args
    params = args[0] if args else kwargs.get("params")
    assert params[0].token_id == "tok_a"
    assert params[0].side == "SELL"


def test_batch_prices_empty_returns_empty():
    import core.polymarket_client as pm
    assert pm.batch_prices([], side="SELL") == {}


def test_batch_prices_invalid_side_raises():
    import core.polymarket_client as pm
    with pytest.raises(ValueError):
        pm.batch_prices(["tok_a"], side="NOT_A_SIDE")
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_polymarket_client.py -v -k "prices" 2>&1 | tail -20`
Expected: three prices tests FAIL.

- [ ] **Step 3: Replace the `batch_prices` stub**

Note: `py_clob_client.get_prices` returns a nested dict `{token_id: {"BUY": str, "SELL": str}}` per side-per-token. We take one side out.

```python
def batch_prices(token_ids: list[str], side: str = "SELL") -> dict[str, float]:
    """Fetch best price for each token on the requested side.

    side: "BUY" (best bid) or "SELL" (best ask).
    Returns {token_id: price_float}. Unknown tokens omitted.
    """
    if side not in ("BUY", "SELL"):
        raise ValueError(f"side must be BUY or SELL, got {side!r}")
    if not token_ids:
        return {}
    client = _get_client()
    params = [BookParams(token_id=tid, side=side) for tid in token_ids]
    resp = retry_with_backoff(
        lambda: client.get_prices(params=params),
        retries=RETRIES, backoff_ms=BACKOFF_MS,
    )
    out: dict[str, float] = {}
    if isinstance(resp, dict):
        for tid, sides in resp.items():
            val = sides.get(side) if isinstance(sides, dict) else sides
            try:
                out[str(tid)] = float(val)
            except (TypeError, ValueError):
                logger.warning("batch_prices: unparseable token=%s side=%s val=%r", tid, side, val)
    return out
```

- [ ] **Step 4: Run tests**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_polymarket_client.py -v -k "prices" 2>&1 | tail -20`
Expected: three prices tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/polymarket_client.py sports_bot_v2/tests/core/test_polymarket_client.py
git commit -m "sports_bot_v2: polymarket_client.batch_prices (BUY|SELL side)

STAIR_A_BATCH_ENDPOINTS_001 step 3 of 6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Implement `batch_spreads`

**Files:**
- Modify: `core/polymarket_client.py`
- Modify: `tests/core/test_polymarket_client.py`

- [ ] **Step 1: Append failing test**

Append to `tests/core/test_polymarket_client.py`:

```python
def test_batch_spreads_casts_and_omits_garbage():
    import core.polymarket_client as pm
    pm._client = None
    fake_client = MagicMock()
    fake_client.get_spreads.return_value = {"tok_a": "0.02", "tok_b": "not_a_number"}
    with patch("core.polymarket_client._get_client", return_value=fake_client):
        out = pm.batch_spreads(["tok_a", "tok_b"])
    assert out == {"tok_a": 0.02}


def test_batch_spreads_empty_returns_empty():
    import core.polymarket_client as pm
    assert pm.batch_spreads([]) == {}
```

- [ ] **Step 2: Run tests (should fail)**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_polymarket_client.py -v -k "spreads" 2>&1 | tail -20`
Expected: two tests FAIL.

- [ ] **Step 3: Replace the `batch_spreads` stub**

```python
def batch_spreads(token_ids: list[str]) -> dict[str, float]:
    """Fetch bid-ask spread for each token. Returns {token_id: spread_float}."""
    if not token_ids:
        return {}
    client = _get_client()
    params = [BookParams(token_id=tid) for tid in token_ids]
    resp = retry_with_backoff(
        lambda: client.get_spreads(params=params),
        retries=RETRIES, backoff_ms=BACKOFF_MS,
    )
    out: dict[str, float] = {}
    if isinstance(resp, dict):
        for tid, spr in resp.items():
            try:
                out[str(tid)] = float(spr)
            except (TypeError, ValueError):
                logger.warning("batch_spreads: unparseable token=%s val=%r", tid, spr)
    return out
```

- [ ] **Step 4: Run tests**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_polymarket_client.py -v -k "spreads" 2>&1 | tail -20`
Expected: two tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/polymarket_client.py sports_bot_v2/tests/core/test_polymarket_client.py
git commit -m "sports_bot_v2: polymarket_client.batch_spreads

STAIR_A_BATCH_ENDPOINTS_001 step 4 of 6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Implement `last_trade_price`

**Files:**
- Modify: `core/polymarket_client.py`
- Modify: `tests/core/test_polymarket_client.py`

- [ ] **Step 1: Append failing test**

Append:

```python
def test_last_trade_price_parses_price_and_ts():
    import core.polymarket_client as pm
    pm._client = None
    fake_client = MagicMock()
    fake_client.get_last_trade_price.return_value = {"price": "0.57", "timestamp": "1716000000"}
    with patch("core.polymarket_client._get_client", return_value=fake_client):
        out = pm.last_trade_price("tok_a")
    assert out == (0.57, 1716000000)


def test_last_trade_price_returns_none_on_empty():
    import core.polymarket_client as pm
    pm._client = None
    fake_client = MagicMock()
    fake_client.get_last_trade_price.return_value = {}
    with patch("core.polymarket_client._get_client", return_value=fake_client):
        out = pm.last_trade_price("tok_a")
    assert out is None
```

- [ ] **Step 2: Run tests (should fail)**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_polymarket_client.py -v -k "last_trade" 2>&1 | tail -20`
Expected: two tests FAIL.

- [ ] **Step 3: Replace stub**

```python
def last_trade_price(token_id: str) -> tuple[float, int] | None:
    """Return (price, unix_ts) of the last executed trade for a token.
    Returns None if the market has no trades yet."""
    client = _get_client()
    resp = retry_with_backoff(
        lambda: client.get_last_trade_price(token_id=token_id),
        retries=RETRIES, backoff_ms=BACKOFF_MS,
    )
    if not isinstance(resp, dict) or not resp:
        return None
    raw_price = resp.get("price")
    raw_ts = resp.get("timestamp") or resp.get("ts") or 0
    try:
        return (float(raw_price), int(float(raw_ts)))
    except (TypeError, ValueError):
        logger.warning("last_trade_price: unparseable token=%s resp=%r", token_id, resp)
        return None
```

- [ ] **Step 4: Run tests**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_polymarket_client.py -v -k "last_trade" 2>&1 | tail -20`
Expected: two tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/polymarket_client.py sports_bot_v2/tests/core/test_polymarket_client.py
git commit -m "sports_bot_v2: polymarket_client.last_trade_price

STAIR_A_BATCH_ENDPOINTS_001 step 5 of 6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Implement `tick_size` with disk-persisted cache + `refresh_tick_sizes`

**Files:**
- Modify: `core/polymarket_client.py`
- Modify: `tests/core/test_polymarket_client.py`

- [ ] **Step 1: Append failing tests**

Append:

```python
def test_tick_size_fetches_caches_and_persists(tmp_path, monkeypatch):
    import core.polymarket_client as pm
    cache_path = tmp_path / "ticks.json"
    monkeypatch.setattr(pm, "TICK_SIZE_CACHE_PATH", cache_path)
    # Reset module-level state
    pm._client = None
    pm._tick_cache = {}
    pm._tick_cache_loaded = False

    fake_client = MagicMock()
    fake_client.get_tick_size.return_value = "0.01"
    with patch("core.polymarket_client._get_client", return_value=fake_client):
        t1 = pm.tick_size("tok_a")
        t2 = pm.tick_size("tok_a")  # cache hit
    assert t1 == 0.01 and t2 == 0.01
    assert fake_client.get_tick_size.call_count == 1
    # Persisted to disk
    assert cache_path.exists()
    assert json.loads(cache_path.read_text()) == {"tok_a": 0.01}


def test_tick_size_loads_from_disk_on_cold_start(tmp_path, monkeypatch):
    import core.polymarket_client as pm
    cache_path = tmp_path / "ticks.json"
    cache_path.write_text(json.dumps({"tok_a": 0.001}))
    monkeypatch.setattr(pm, "TICK_SIZE_CACHE_PATH", cache_path)
    pm._client = None
    pm._tick_cache = {}
    pm._tick_cache_loaded = False

    fake_client = MagicMock()
    with patch("core.polymarket_client._get_client", return_value=fake_client):
        t = pm.tick_size("tok_a")
    assert t == 0.001
    fake_client.get_tick_size.assert_not_called()


def test_refresh_tick_sizes_only_fetches_missing(tmp_path, monkeypatch):
    import core.polymarket_client as pm
    monkeypatch.setattr(pm, "TICK_SIZE_CACHE_PATH", tmp_path / "ticks.json")
    pm._client = None
    pm._tick_cache = {"tok_a": 0.01}
    pm._tick_cache_loaded = True

    fake_client = MagicMock()
    fake_client.get_tick_size.side_effect = lambda token_id: "0.001"
    with patch("core.polymarket_client._get_client", return_value=fake_client):
        n = pm.refresh_tick_sizes(["tok_a", "tok_b", "tok_c"])
    assert n == 2  # tok_b + tok_c fetched; tok_a cached
    assert fake_client.get_tick_size.call_count == 2
    assert pm._tick_cache["tok_b"] == 0.001
    assert pm._tick_cache["tok_c"] == 0.001
```

- [ ] **Step 2: Run tests (should fail)**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_polymarket_client.py -v -k "tick" 2>&1 | tail -30`
Expected: three tick tests FAIL.

- [ ] **Step 3: Replace stubs**

```python
def tick_size(token_id: str) -> float:
    """Return tick size (minimum price increment) for a token.

    Result is cached in-memory AND persisted to TICK_SIZE_CACHE_PATH so it
    survives process restarts. First call per token hits the CLOB; subsequent
    calls serve from cache.
    """
    _load_tick_cache()
    if token_id in _tick_cache:
        return _tick_cache[token_id]
    client = _get_client()
    resp = retry_with_backoff(
        lambda: client.get_tick_size(token_id=token_id),
        retries=RETRIES, backoff_ms=BACKOFF_MS,
    )
    try:
        tick = float(resp)
    except (TypeError, ValueError):
        logger.warning("tick_size: unparseable token=%s resp=%r; defaulting to 0.01", token_id, resp)
        tick = 0.01
    _tick_cache[token_id] = tick
    _save_tick_cache()
    return tick


def refresh_tick_sizes(token_ids: list[str]) -> int:
    """Prefetch tick sizes for multiple tokens. Returns count of tokens newly fetched.

    Tokens already in cache are skipped. Fetch failures log a warning and do
    not abort the batch.
    """
    _load_tick_cache()
    fetched = 0
    for tid in token_ids:
        if tid in _tick_cache:
            continue
        try:
            tick_size(tid)  # writes to cache + disk
            fetched += 1
        except Exception as exc:
            logger.warning("refresh_tick_sizes: fetch failed token=%s err=%s", tid, exc)
    return fetched
```

- [ ] **Step 4: Run tests**

Run: `"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/core/test_polymarket_client.py -v 2>&1 | tail -25`
Expected: all 14+ tests in the file PASS.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/core/polymarket_client.py sports_bot_v2/tests/core/test_polymarket_client.py
git commit -m "sports_bot_v2: polymarket_client tick_size + refresh_tick_sizes

In-memory cache backed by runtime/tick_sizes.json on disk; survives
process restarts. refresh_tick_sizes prefetches for a batch of tokens
and skips those already cached.

STAIR_A_BATCH_ENDPOINTS_001 step 6 of 6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Wire `refresh_tick_sizes` into bot_core discovery

**Files:**
- Modify: `bot_core.py` (discovery path, both initial and refresh)

Context: in Task 1 of the original 2026-04-20 session we added `_sync_market_stream(_markets)` immediately after each discovery in `bot_core.py`. We mirror that pattern for tick sizes.

- [ ] **Step 1: Read current bot_core discovery region**

Open `bot_core.py`. Find two call sites (search for `discover_markets(`): one in `main()` initial (around line 420) and one in the per-loop refresh branch (around line 455). Both end with `_sync_market_stream(_markets)`.

- [ ] **Step 2: Add helper right next to `_sync_market_stream`**

Find the `_sync_market_stream` function (added in 2026-04-20 session). Immediately after it, add:

```python
def _refresh_tick_sizes_for_markets(markets: list[Market]) -> None:
    try:
        from core.polymarket_client import refresh_tick_sizes
        token_ids: list[str] = []
        for m in markets:
            if not m.active or m.closed or m.market_type != "moneyline":
                continue
            if m.yes_token_id:
                token_ids.append(str(m.yes_token_id))
            if m.no_token_id:
                token_ids.append(str(m.no_token_id))
        if token_ids:
            n = refresh_tick_sizes(token_ids)
            logger.info("tick_size refresh: requested=%d new_fetches=%d", len(token_ids), n)
    except Exception as exc:
        logger.warning("tick_size refresh failed: %s", exc)
```

- [ ] **Step 3: Call it after each `_sync_market_stream` site**

Find both lines `_sync_market_stream(_markets)`. After each, insert:

```python
                _refresh_tick_sizes_for_markets(_markets)
```

(Match the surrounding indentation exactly — inside the `try` block, same level as the preceding `_sync_market_stream` call.)

- [ ] **Step 4: Syntax check**

Run: `cd "C:/Users/johnny/Desktop/sports_bot_v2" && "C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -c "import ast; ast.parse(open('bot_core.py').read()); print('OK')"`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/bot_core.py
git commit -m "sports_bot_v2: refresh tick-size cache on discovery in bot_core

After every discover_markets call, call polymarket_client.refresh_tick_sizes
for every live moneyline market's yes+no token. First-run cold-cache will
fetch ~360 ticks; subsequent loops are no-ops.

STAIR_A_BATCH_ENDPOINTS_001.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Add `USE_BATCH_PRICES` feature flag + batch OB-scan path

**Files:**
- Modify: `bot_core.py` (OB scan region around line 490–545)

This task swaps the existing 180-parallel-HTTP fanout for a single batched `batch_midpoints` + `batch_prices` call when the flag is on. The `/book` walk is retained for the single market we're about to trade — that's still needed for VWAP fill estimation. The flag defaults OFF so nothing breaks for existing operators.

- [ ] **Step 1: Read the current OB scan block**

Open `bot_core.py` around lines 490–545. Locate the region starting with `# Parallel orderbook scan:` and ending at `for market, ob, err in _scan_results:`. Note how `_scan_results` is consumed (`append_jsonl` + state tracking).

- [ ] **Step 2: Add the flag near other config**

Near the top of `bot_core.py` (around line 25–45, in the config block), add:

```python
USE_BATCH_PRICES = os.getenv("USE_BATCH_PRICES", "false").strip().lower() in {"1", "true", "yes", "on"}
```

- [ ] **Step 3: Build a shim that produces OB-snapshot-shaped entries from batch calls**

`OBSnapshot` (see `core/types.py:34`) has these fields, in this order:
- `bid_yes, ask_yes, bid_no, ask_no` — all `float | None`
- `spread_yes, spread_no` — `float | None`
- `depth_top5_usd_yes, depth_top5_usd_no` — `float` (NOT optional; 0.0 signals unknown)
- `imbalance` — `float` (0.0 = balanced)
- `micro_ok` — `bool`
- `micro_reason` — `str`
- `fetched_at` — `str` (default `""`)
- `bid_levels_yes, ask_levels_yes, bid_levels_no, ask_levels_no` — `list[dict]` (default `[]`)

In `bot_core.py`, right above the `main()` function (near the other helpers like `_sync_market_stream`), add:

```python
def _batch_ob_scan(markets: list[Market]) -> list[tuple[Market, "OBSnapshot | None", Exception | None]]:
    """Lightweight OB scan using batched midpoints+prices instead of 180 /book GETs.

    Returns the same (market, OBSnapshot, err) tuple shape the per-loop code
    consumes; OBSnapshot here carries best-bid/best-ask/mid, no depth levels.
    Depth is fetched on demand by the single market we're about to trade.

    The caller (`markets` arg) is already filtered — this fn does not re-filter.
    """
    from core.polymarket_client import batch_midpoints, batch_prices
    from core.types import OBSnapshot

    token_ids: list[str] = []
    for m in markets:
        if m.yes_token_id:
            token_ids.append(str(m.yes_token_id))
        if m.no_token_id:
            token_ids.append(str(m.no_token_id))

    try:
        asks = batch_prices(token_ids, side="SELL")
        bids = batch_prices(token_ids, side="BUY")
        _ = batch_midpoints(token_ids)  # cached for other consumers; not stored per-market
    except Exception as exc:
        logger.warning("batch_ob_scan: batched fetch failed err=%s; caller should fall back", exc)
        return [(m, None, exc) for m in markets]

    fetched_at = now_iso()
    out: list[tuple[Market, OBSnapshot | None, Exception | None]] = []
    for m in markets:
        yid, nid = str(m.yes_token_id or ""), str(m.no_token_id or "")
        bid_yes = bids.get(yid)
        ask_yes = asks.get(yid)
        bid_no = bids.get(nid)
        ask_no = asks.get(nid)
        spread_yes = (ask_yes - bid_yes) if (ask_yes is not None and bid_yes is not None) else None
        spread_no = (ask_no - bid_no) if (ask_no is not None and bid_no is not None) else None
        ob = OBSnapshot(
            bid_yes=bid_yes,
            ask_yes=ask_yes,
            bid_no=bid_no,
            ask_no=ask_no,
            spread_yes=spread_yes,
            spread_no=spread_no,
            depth_top5_usd_yes=0.0,
            depth_top5_usd_no=0.0,
            imbalance=0.0,
            micro_ok=True,
            micro_reason="batched_no_depth",
            fetched_at=fetched_at,
            # bid_levels_* / ask_levels_* default to [] — batch path has no depth
        )
        out.append((m, ob, None))
    return out
```

- [ ] **Step 4: Branch the main-loop scan on the flag**

In `bot_core.py`, find this existing block (search for the string `_scan_workers = int(os.getenv`). The current shape is:

```python
            _scan_workers = int(os.getenv("OB_SCAN_WORKERS", "20"))
            _scan_t0 = time.monotonic()

            def _scan_one(market):
                try:
                    return market, get_orderbook_snapshot(market), None
                except Exception as e:
                    return market, None, e

            with ThreadPoolExecutor(max_workers=max(1, _scan_workers)) as _pool:
                _scan_results = list(_pool.map(_scan_one, _scan_targets))

            logger.info(
                "OB_SCAN n=%d workers=%d elapsed=%.2fs",
                len(_scan_results), _scan_workers, time.monotonic() - _scan_t0,
            )

            for market, ob, err in _scan_results:
```

Replace only the parts up to (and NOT including) the `for market, ob, err in _scan_results:` line with:

```python
            _scan_t0 = time.monotonic()

            if USE_BATCH_PRICES:
                _scan_results = _batch_ob_scan(_scan_targets)
                logger.info(
                    "OB_SCAN (batch) n=%d elapsed=%.2fs",
                    len(_scan_results), time.monotonic() - _scan_t0,
                )
            else:
                _scan_workers = int(os.getenv("OB_SCAN_WORKERS", "20"))

                def _scan_one(market):
                    try:
                        return market, get_orderbook_snapshot(market), None
                    except Exception as e:
                        return market, None, e

                with ThreadPoolExecutor(max_workers=max(1, _scan_workers)) as _pool:
                    _scan_results = list(_pool.map(_scan_one, _scan_targets))

                logger.info(
                    "OB_SCAN n=%d workers=%d elapsed=%.2fs",
                    len(_scan_results), _scan_workers, time.monotonic() - _scan_t0,
                )

            for market, ob, err in _scan_results:
```

The `for market, ob, err in _scan_results:` loop below is unchanged; both branches populate `_scan_results` the same way.

- [ ] **Step 5: Syntax check**

Run: `cd "C:/Users/johnny/Desktop/sports_bot_v2" && "C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -c "import ast; ast.parse(open('bot_core.py').read()); print('OK')"`
Expected: `OK`.

- [ ] **Step 6: Start bot with flag OFF to prove zero regression**

```bash
cd "C:/Users/johnny/Desktop/sports_bot_v2"
# Make sure USE_BATCH_PRICES is NOT in .env (default off)
"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -c "from bot_core import USE_BATCH_PRICES; assert USE_BATCH_PRICES is False, 'default must be off'; print('flag default OK')"
```
Expected: `flag default OK`.

- [ ] **Step 7: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/bot_core.py
git commit -m "sports_bot_v2: USE_BATCH_PRICES flag + _batch_ob_scan path

Adds opt-in batch OB-scan path that uses polymarket_client.batch_midpoints +
batch_prices instead of 180 parallel /book GETs. Feature-flagged off by
default. Depth levels are not populated in batch mode — the /book walk is
still called by paper_exec for the one market about to trade.

STAIR_A_BATCH_ENDPOINTS_001.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: Live verification — batch vs. baseline

**Files:** none; runtime observation only.

- [ ] **Step 1: Baseline run (flag OFF) — capture OB_SCAN timings**

Kill existing bot_core (if running), restart via `launch_all.py`. Let it run 3 loops (~45s). Collect:

```bash
grep "OB_SCAN" "C:/Users/johnny/Desktop/sports_bot_v2/logs/bot_core_launcher.log" | tail -5
```
Record typical elapsed (should be ~3–4s with 40 workers).

- [ ] **Step 2: Switch flag ON**

Edit `.env`, add line:
```
USE_BATCH_PRICES=true
```

Kill bot_core PID (launcher will respawn):

```bash
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*bot_core.py*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }"
```

- [ ] **Step 3: Batch run — capture timings + correctness**

Wait one full discovery refresh cycle (~3 loops). Then:

```bash
grep -E "OB_SCAN \(batch\)|tick_size refresh" "C:/Users/johnny/Desktop/sports_bot_v2/logs/bot_core_launcher.log" | tail -5
```

Expected:
- `OB_SCAN (batch) n=180 elapsed=<1.0s` (should be far faster than baseline)
- `tick_size refresh` reports `new_fetches=0` after first refresh (cache warmed)
- No new ERROR lines

- [ ] **Step 4: Verify recommendations still flow**

```bash
grep "BRIDGE GATE PASS" "C:/Users/johnny/Desktop/sports_bot_v2/logs/bot_core_launcher.log" | tail -3
```

Expected: bridge passes are still happening for active live games (same as baseline). If passes DROPPED to zero when flag flipped, something in the batch path isn't delivering prices the bridge's stale_quote guard can use. Debug: compare `_batch_ob_scan` output fields with the dataclass the per-loop code expects.

- [ ] **Step 5: Check tick cache on disk**

```bash
ls -la "C:/Users/johnny/Desktop/sports_bot_v2/runtime/tick_sizes.json" 2>&1
"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -c "import json; d = json.load(open('runtime/tick_sizes.json')); print(f'cached_tokens={len(d)} sample={list(d.items())[:3]}')"
```

Expected: file exists with ~360 token entries (180 markets × 2 sides), each valued 0.01 or 0.001.

- [ ] **Step 6: Commit observation notes**

Create `docs/superpowers/plans/2026-04-21-polymarket-stair-a-verification.md` with timings observed in Steps 1 and 3 (baseline elapsed vs batch elapsed). Commit:

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/docs/superpowers/plans/2026-04-21-polymarket-stair-a-verification.md sports_bot_v2/runtime/tick_sizes.json
git commit -m "sports_bot_v2: Stair A verification — batch scan timings + tick cache

Records OB_SCAN elapsed baseline-vs-batch and confirms tick_sizes.json
cache populated on first live run.

STAIR_A_BATCH_ENDPOINTS_001 observation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

Note: `runtime/tick_sizes.json` will be committed only if not gitignored. If `runtime/` is in `.gitignore` (likely), omit that path.

---

## Task 12: Document new env vars + pin py_clob_client

**Files:**
- Modify: `.env.example`
- Modify: `requirements.txt`

- [ ] **Step 1: Update `.env.example`**

Append to `.env.example`:

```
# ── Polymarket integration (Stair A) ───────────────────────────────────────
# Toggles the batched midpoints+prices OB-scan path. Off = legacy parallel /book.
USE_BATCH_PRICES=false
# CLOB host override (only change for staging/testing)
CLOB_HOST=https://clob.polymarket.com
# Polygon chain id (137 = mainnet)
POLYGON_CHAIN_ID=137
# On-disk tick-size cache path (relative to sports_bot_v2/)
TICK_SIZE_CACHE_PATH=runtime/tick_sizes.json
# Retry tuning for polymarket_client
POLYMARKET_CLIENT_RETRIES=3
POLYMARKET_CLIENT_BACKOFF_MS=500
```

- [ ] **Step 2: Pin py_clob_client in `requirements.txt`**

Replace the file content with:

```
flask>=3.0,<4.0
py_clob_client>=0.34,<0.35
```

- [ ] **Step 3: Verify install from requirements**

```bash
cd "C:/Users/johnny/Desktop/sports_bot_v2"
"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pip install -r requirements.txt 2>&1 | tail -5
```

Expected: `Requirement already satisfied` for both (no new install needed, deps are already present in the global env).

- [ ] **Step 4: Run full test suite to confirm nothing regressed**

```bash
cd "C:/Users/johnny/Desktop/sports_bot_v2"
"C:/Users/johnny/AppData/Local/Python/pythoncore-3.14-64/python.exe" -m pytest tests/ -v 2>&1 | tail -20
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/johnny/Desktop"
git add sports_bot_v2/.env.example sports_bot_v2/requirements.txt
git commit -m "sports_bot_v2: document Polymarket env vars + pin py_clob_client

.env.example gains USE_BATCH_PRICES, CLOB_HOST, POLYGON_CHAIN_ID,
TICK_SIZE_CACHE_PATH, POLYMARKET_CLIENT_{RETRIES,BACKOFF_MS}.
requirements.txt pins py_clob_client>=0.34,<0.35 so test runs are
reproducible.

STAIR_A_BATCH_ENDPOINTS_001 closeout.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Definition of Done for Stair A

- [ ] All unit tests in `tests/core/test_utils_retry.py` and `tests/core/test_polymarket_client.py` pass
- [ ] `bot_core.py` has `USE_BATCH_PRICES` branch; flag defaults OFF; existing per-market scan path unchanged when flag is OFF
- [ ] `runtime/tick_sizes.json` populates after first live run with ~360 entries
- [ ] Batch OB scan measured <1.0s elapsed in live verification (vs. ~3.6s baseline)
- [ ] 30-min live run with flag ON shows bridge passes still happening; no new ERROR lines
- [ ] `.env.example` and `requirements.txt` updated and committed
- [ ] 9 commits total (one per Task 2–10, plus verification Task 11 and closeout Task 12)

## Follow-ups (NOT in this plan; belong to later stairs)

- **Stair C** will use `polymarket_client.tick_size()` to snap order prices before placement
- **Stair B** will add `signed` endpoints to `polymarket_client` (`user_stream` auth via `create_or_derive_api_key`)
- **Stair D** will add `/positions` and `/trades` (mine) to `polymarket_client`
- **Dashboard enrichment**: surface `OB_SCAN (batch) elapsed` on dugout_dash's status panel (separate task, not load-bearing for Stair A)
