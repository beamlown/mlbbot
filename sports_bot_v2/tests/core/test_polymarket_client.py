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
