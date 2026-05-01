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
