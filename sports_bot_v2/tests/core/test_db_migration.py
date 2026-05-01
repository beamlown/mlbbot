"""Test that db.init_db() adds order_id column idempotently."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


def test_init_db_adds_order_id_column(tmp_path, monkeypatch):
    """Running init_db() against an old-schema trades table must ADD order_id
    without dropping data."""
    # Arrange: make an old-schema trades table with one row
    db_path = tmp_path / "t.db"
    con = sqlite3.connect(db_path)
    # Old-schema trades table: includes columns referenced by existing indexes
    # (market_id, sport) so init_db's index creation doesn't blow up, but omits
    # order_id so we can verify the new migration adds it.
    con.execute("""
        CREATE TABLE trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_open TEXT,
            market_slug TEXT,
            market_id TEXT,
            side TEXT,
            entry_px REAL,
            status TEXT,
            sport TEXT
        )
    """)
    con.execute("INSERT INTO trades (ts_open, market_slug, side, entry_px, status) VALUES (?, ?, ?, ?, ?)",
                ("2026-04-21T00:00:00", "mlb-test-2026-04-21", "BUY_YES", 0.55, "open"))
    con.commit()
    con.close()

    # Act: run init_db pointed at this file
    monkeypatch.setenv("DB_PATH", str(db_path))
    import importlib, core.db
    importlib.reload(core.db)
    core.db.init_db()

    # Assert: order_id column exists; old row survived with order_id=NULL
    con = sqlite3.connect(db_path)
    cols = [r[1] for r in con.execute("PRAGMA table_info(trades)").fetchall()]
    assert "order_id" in cols
    row = con.execute("SELECT market_slug, order_id FROM trades WHERE side='BUY_YES'").fetchone()
    assert row == ("mlb-test-2026-04-21", None)
    con.close()


def test_init_db_is_idempotent(tmp_path, monkeypatch):
    """Running init_db() twice must not error or duplicate columns."""
    db_path = tmp_path / "t2.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    import importlib, core.db
    importlib.reload(core.db)
    core.db.init_db()
    core.db.init_db()  # second call must be a no-op
    con = sqlite3.connect(db_path)
    cols = [r[1] for r in con.execute("PRAGMA table_info(trades)").fetchall()]
    assert cols.count("order_id") == 1
    con.close()


def test_insert_trade_persists_order_id(tmp_path, monkeypatch):
    """Trade with order_id set must round-trip through insert + fetch."""
    db_path = tmp_path / "t3.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    import importlib, core.db, core.types
    importlib.reload(core.db)
    importlib.reload(core.types)
    core.db.init_db()

    # status='open' required for fetch_open_trades() to find the row (WHERE status='open')
    trade = core.types.Trade(
        id=None,
        ts_open="2026-04-21T00:00:00+00:00",
        ts_close=None,
        market_slug="mlb-test-2026-04-21",
        market_id="0xtest",
        side="BUY_YES",
        qty=100.0,
        entry_px=0.55,
        exit_px=None,
        pnl_usd=None,
        fees_usd=0.0,
        reason_open="",
        reason_close=None,
        confidence=0.5,
        mode="neutral",
        status="open",
        source="live",
        actual_fill_px=0.0,
        order_id="0xpoly_order_abc123",
    )
    core.db.insert_open_trade(trade)

    open_trades = core.db.fetch_open_trades()
    assert len(open_trades) == 1
    assert open_trades[0].order_id == "0xpoly_order_abc123"


def test_insert_open_trade_respects_trade_status(tmp_path, monkeypatch):
    """insert_open_trade must use trade.status, not hardcode 'open'. Enables
    Stair C live mode to insert rows with status='pending'."""
    db_path = tmp_path / "t5.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    import importlib, core.db, core.types
    importlib.reload(core.db)
    importlib.reload(core.types)
    core.db.init_db()

    trade = core.types.Trade(
        id=None, ts_open="2026-04-23T00:00:00+00:00", ts_close=None,
        market_slug="mlb-test-2026-04-23", market_id="0xm1",
        side="BUY_YES", qty=100.0, entry_px=0.55, exit_px=None,
        pnl_usd=None, fees_usd=0.0, reason_open="", reason_close=None,
        confidence=0.5, mode="neutral", status="pending", source="live",
        actual_fill_px=0.0, order_id="0xlive_abc",
    )
    core.db.insert_open_trade(trade)

    # Query raw to confirm what was persisted
    import sqlite3
    con = sqlite3.connect(db_path)
    row = con.execute("SELECT status, order_id FROM trades").fetchone()
    assert row == ("pending", "0xlive_abc"), f"expected ('pending', '0xlive_abc'), got {row}"


def test_insert_trade_with_no_order_id_defaults_to_none(tmp_path, monkeypatch):
    """Paper trades have order_id=None. Must persist as NULL and fetch back as None."""
    db_path = tmp_path / "t4.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    import importlib, core.db, core.types
    importlib.reload(core.db)
    importlib.reload(core.types)
    core.db.init_db()

    trade = core.types.Trade(
        id=None, ts_open="2026-04-21T00:00:00+00:00", ts_close=None,
        market_slug="mlb-paper-2026-04-21", market_id="0xpaper",
        side="BUY_NO", qty=50.0, entry_px=0.45, exit_px=None,
        pnl_usd=None, fees_usd=0.0, reason_open="", reason_close=None,
        confidence=0.4, mode="neutral", status="open", source="bot",
        actual_fill_px=0.0,
        # order_id defaults to None
    )
    core.db.insert_open_trade(trade)
    open_trades = core.db.fetch_open_trades()
    assert len(open_trades) == 1
    assert open_trades[0].order_id is None
