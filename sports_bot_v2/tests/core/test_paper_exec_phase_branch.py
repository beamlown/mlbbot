"""Tests for paper_exec.open_position PHASE branching."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _build_inputs():
    """Minimal Market, Signal, OBSnapshot for open_position."""
    from core.types import Market, Signal, OBSnapshot
    market = Market(
        market_id="0xm1",
        event_slug="evt-mlb-test-2026-04-23",
        slug="mlb-test-2026-04-23",
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
        fetched_at="2026-04-23T00:00:00",
        bid_levels_yes=[{"price": 0.50, "size": 1000.0}],
        ask_levels_yes=[{"price": 0.55, "size": 1000.0}],
        bid_levels_no=[{"price": 0.45, "size": 1000.0}],
        ask_levels_no=[{"price": 0.50, "size": 1000.0}],
    )
    return market, signal, ob


def test_paper_phase_returns_open_trade_unchanged(monkeypatch):
    """Default PHASE=paper: open_position behavior unchanged.

    Paper path is the running bot's code. This test catches subtle regressions:
    sizing, fill-price, VWAP walk, fees, or reason_open format drifting.
    """
    monkeypatch.setenv("PHASE", "paper")
    import importlib, core.paper_exec
    importlib.reload(core.paper_exec)

    market, signal, ob = _build_inputs()
    trade = core.paper_exec.open_position(market, signal, ob)

    # Status/order_id — the new PHASE-branch surface
    assert trade is not None, "paper mode must return a Trade"
    assert trade.status == "open", f"paper trade status drifted: {trade.status!r}"
    assert trade.order_id is None, "paper trade must not have a live order_id"

    # Fill computation — regression-catcher for sizing/VWAP/fees paths
    assert trade.entry_px > 0.0, "entry_px must be computed from the book"
    assert trade.qty > 0.0, "qty must be sized from size_usd / entry_px"
    assert trade.fees_usd > 0.0, "paper fees must apply (PAPER_FEE_PCT > 0)"
    assert trade.actual_fill_px > 0.0, "actual_fill_px populated from _fill_price_entry"

    # reason_open format — must not contain the live-mode suffix
    assert trade.reason_open.startswith("sig=BUY_YES"), (
        f"reason_open format drifted; got: {trade.reason_open!r}"
    )
    assert "live_order_id=" not in trade.reason_open, (
        "paper mode must not append live_order_id suffix"
    )


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
