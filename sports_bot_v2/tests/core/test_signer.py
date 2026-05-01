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
