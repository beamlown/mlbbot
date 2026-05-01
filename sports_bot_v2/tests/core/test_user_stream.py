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


def test_trade_event_updates_sqlite_row(tmp_path, monkeypatch):
    """A TRADE event whose maker_orders[].order_id matches a pending sqlite
    row must trigger update_trade_fill and transition status pending→open."""
    db_path = tmp_path / "t.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    import importlib, core.db, core.types, core.user_stream, json as _json
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
    fake_event = _json.dumps({
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
    import importlib, core.db, core.user_stream, json as _json
    importlib.reload(core.db)
    importlib.reload(core.user_stream)
    core.db.init_db()

    client = core.user_stream.UserStreamClient()
    fake_event = _json.dumps({
        "event_type": "trade",
        "market": "0xmk",
        "price": "0.50",
        "maker_orders": [{"order_id": "0xnobody_knows", "matched_amount": "100", "price": "0.50"}],
    })
    client._on_message(None, fake_event)

    assert core.db.fetch_open_trades() == []
    assert client.debug_status()["trade_events_seen"] == 1


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
