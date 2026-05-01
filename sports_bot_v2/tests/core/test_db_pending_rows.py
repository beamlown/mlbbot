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
