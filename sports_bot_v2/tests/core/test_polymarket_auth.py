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
