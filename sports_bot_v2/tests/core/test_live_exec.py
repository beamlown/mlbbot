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


def test_kill_switch_engages_on_unknown_value(monkeypatch):
    """SECURITY: any value NOT in the explicit 'off' set must engage the kill
    switch (fail-safe default). A typo in the env var cannot accidentally lift
    the safety."""
    monkeypatch.setenv("PHASE", "live")
    monkeypatch.setenv("LIVE_TRADING_KILL_SWITCH", "enable_please")  # typo
    import importlib, core.live_exec
    importlib.reload(core.live_exec)
    result = core.live_exec.place_order(side="BUY", token_id="tok_a", price=0.55, size_usd=50.0)
    assert result.status == "rejected"
    assert result.reason == "kill_switch"


def test_kill_switch_engages_on_empty_string(monkeypatch):
    """SECURITY: empty LIVE_TRADING_KILL_SWITCH must engage the kill switch."""
    monkeypatch.setenv("PHASE", "live")
    monkeypatch.setenv("LIVE_TRADING_KILL_SWITCH", "")
    import importlib, core.live_exec
    importlib.reload(core.live_exec)
    result = core.live_exec.place_order(side="BUY", token_id="tok_a", price=0.55, size_usd=50.0)
    assert result.status == "rejected"
    assert result.reason == "kill_switch"


def test_kill_switch_lifts_on_explicit_false(monkeypatch):
    """Sanity: explicit 'false' must lift the switch (otherwise we'd never be
    able to go live at all)."""
    monkeypatch.setenv("PHASE", "live")
    monkeypatch.setenv("LIVE_TRADING_KILL_SWITCH", "false")
    import importlib, core.live_exec
    importlib.reload(core.live_exec)
    # We should NOT see 'kill_switch' reason — it should advance to signer check
    from core.signer import DummySigner
    with patch("core.live_exec.tick_size", return_value=0.01):
        result = core.live_exec.place_order(
            side="BUY", token_id="tok_a", price=0.55, size_usd=50.0,
            signer=DummySigner(),
        )
    assert result.status == "rejected"
    assert result.reason == "signer_not_ready"  # advanced past kill_switch gate


def test_place_order_returns_error_when_sign_order_raises(monkeypatch):
    """I-1 regression: if signer.sign_order raises, place_order must return
    OrderResult(status='error', ...) per its documented contract — not
    propagate the exception."""
    monkeypatch.setenv("PHASE", "live")
    monkeypatch.setenv("LIVE_TRADING_KILL_SWITCH", "false")
    import importlib, core.live_exec
    importlib.reload(core.live_exec)

    # Build a custom signer that passes is_ready() but raises in sign_order
    class ExplodingSigner:
        def is_ready(self):
            return True
        def sign_order(self, args):
            raise RuntimeError("simulated sign failure")

    with patch("core.live_exec.tick_size", return_value=0.01):
        result = core.live_exec.place_order(
            side="BUY", token_id="tok_a", price=0.55, size_usd=50.0,
            signer=ExplodingSigner(),
        )
    assert result.status == "error"
    assert "sign_or_submit" in result.reason
    assert "simulated sign failure" in result.reason


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
