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
