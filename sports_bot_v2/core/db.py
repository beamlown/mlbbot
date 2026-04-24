"""
core/db.py — SQLite trades_sports.db schema + helpers for sports_bot_v2
"""
from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from typing import Any

from core.types import Trade

logger = logging.getLogger("core.db")

DB_PATH = os.getenv("DB_PATH", "trades_sports.db")
DB_TIMEOUT_MS = int(os.getenv("DB_TIMEOUT_MS", "5000"))
DB_CONNECT_TIMEOUT_SEC = float(os.getenv("DB_CONNECT_TIMEOUT_SEC", "5.0"))

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_open         TEXT NOT NULL,
    ts_close        TEXT,
    market_slug     TEXT NOT NULL,
    market_id       TEXT NOT NULL,
    side            TEXT NOT NULL,
    qty             REAL NOT NULL,
    entry_px        REAL NOT NULL,
    exit_px         REAL,
    pnl_usd         REAL,
    fees_usd        REAL,
    reason_open     TEXT,
    reason_close    TEXT,
    confidence      REAL,
    mode            TEXT,
    status          TEXT NOT NULL DEFAULT 'open',
    sport           TEXT DEFAULT 'unknown'
);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_market  ON trades(market_id);
CREATE INDEX IF NOT EXISTS idx_trades_sport   ON trades(sport);
"""


@contextmanager
def _db_conn(op: str = "db"):
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=DB_CONNECT_TIMEOUT_SEC)
        conn.execute(f"PRAGMA busy_timeout={DB_TIMEOUT_MS}")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        yield conn
    except sqlite3.Error as e:
        logger.error("[DB] %s error: %s", op, e)
        raise
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _ensure_meta_table() -> None:
    """Create meta table if it doesn't exist."""
    with _db_conn("ensure_meta_table") as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()


def _migrate_attribution_schema() -> None:
    """Idempotent migration: add attribution columns to trades table."""
    with _db_conn("migrate_attribution_schema") as conn:
        # Check if columns already exist
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(trades)")
        existing_cols = {row[1] for row in cursor.fetchall()}

        cols_to_add = [
            ("entry_model_prob", "REAL"),
            ("entry_market_prob", "REAL"),
            ("expected_edge_pct", "REAL"),
            ("actual_fill_px", "REAL"),
            ("actual_fill_size", "REAL"),
            ("exit_reason", "TEXT"),
            ("exit_model_prob", "REAL"),
            ("exit_market_prob", "REAL"),
            ("hold_seconds", "INTEGER"),
            ("resolved_winner", "TEXT"),
            ("model_side_was_right", "INTEGER"),
            ("trade_class", "TEXT"),
            ("attribution_version", "INTEGER"),
        ]

        added_cols = []
        for col_name, col_type in cols_to_add:
            if col_name not in existing_cols:
                try:
                    conn.execute(f"ALTER TABLE trades ADD COLUMN {col_name} {col_type}")
                    added_cols.append(col_name)
                except sqlite3.OperationalError as e:
                    logger.warning("Column %s already exists or error: %s", col_name, e)

        if added_cols:
            conn.commit()
            logger.info("DB migration: added attribution columns: %s", added_cols)

        # Add indexes
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_trade_class ON trades(trade_class)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_exit_reason ON trades(exit_reason)")
            conn.commit()
            logger.info("DB migration: added attribution indexes")
        except sqlite3.Error as e:
            logger.warning("DB migration: index creation error: %s", e)


def _update_migration_marker() -> None:
    """Mark attribution schema migration as complete."""
    _ensure_meta_table()
    with _db_conn("update_migration_marker") as conn:
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("attribution_schema_version", "1")
        )
        conn.commit()


def init_db() -> None:
    with _db_conn("init_db") as conn:
        conn.executescript(_CREATE_SQL)
        conn.commit()
    try:
        with _db_conn("check_source_col") as conn:
            _cols = {r[1] for r in conn.execute("PRAGMA table_info(trades)").fetchall()}
        if "source" not in _cols:
            with _db_conn("migrate_source_col") as conn:
                conn.execute("ALTER TABLE trades ADD COLUMN source TEXT DEFAULT 'bot'")
                conn.commit()
            logger.info("DB migration: added source column")
    except sqlite3.OperationalError:
        pass
    try:
        with _db_conn("init_db_open_slug_unique_idx") as conn:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_one_open_per_slug "
                "ON trades(market_slug) WHERE status='open'"
            )
            conn.commit()
        logger.info("DB migration: ensured unique open-slug index")
    except sqlite3.Error as e:
        logger.warning("DB migration: failed to ensure unique open-slug index: %s", e)

    # Run attribution schema migration
    _migrate_attribution_schema()
    _update_migration_marker()

    logger.info("DB initialized at %s", DB_PATH)


def insert_open_trade(trade: Trade, sport: str = "unknown") -> int | None:
    with _db_conn("insert_open_trade") as conn:
        c = conn.cursor()
        conn.execute("BEGIN IMMEDIATE")
        existing = c.execute(
            "SELECT id FROM trades WHERE market_slug=? AND status='open' LIMIT 1",
            (trade.market_slug,),
        ).fetchone()
        if existing is not None:
            conn.rollback()
            return None
        try:
            c.execute(
                """INSERT INTO trades
                   (ts_open, ts_close, market_slug, market_id, side, qty, entry_px,
                    exit_px, pnl_usd, fees_usd, reason_open, reason_close,
                    confidence, mode, status, sport, source)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    trade.ts_open, trade.ts_close,
                    trade.market_slug, trade.market_id,
                    trade.side, trade.qty, trade.entry_px,
                    trade.exit_px, trade.pnl_usd, trade.fees_usd,
                    trade.reason_open, trade.reason_close,
                    trade.confidence, trade.mode,
                    "open", sport, getattr(trade, "source", "bot"),
                ),
            )
            conn.commit()
            row_id = c.lastrowid
            logger.info("Opened trade id=%d %s @ %.4f", row_id, trade.side, trade.entry_px)
            return row_id
        except sqlite3.IntegrityError:
            conn.rollback()
            return None


def close_trade(trade_id: int, close_data: dict) -> None:
    with _db_conn("close_trade") as conn:
        conn.execute(
            """UPDATE trades SET
               ts_close=?, exit_px=?, pnl_usd=?, fees_usd=?,
               reason_close=?, status='closed'
               WHERE id=?""",
            (
                close_data.get("ts_close"),
                close_data.get("exit_px"),
                close_data.get("pnl_usd"),
                close_data.get("fees_usd"),
                close_data.get("reason_close"),
                trade_id,
            ),
        )
        conn.commit()
        logger.info("Closed trade id=%d reason=%s pnl=%.4f",
                    trade_id, close_data.get("reason_close"), close_data.get("pnl_usd", 0.0))


def update_trade_attribution(trade_id: int, attr_data: dict) -> None:
    """Update attribution columns on a trade row. Only updates non-None values."""
    with _db_conn("update_attribution") as conn:
        # Build dynamic UPDATE statement
        cols_to_update = []
        values = []
        for key, val in attr_data.items():
            if val is not None:
                cols_to_update.append(f"{key}=?")
                values.append(val)

        if not cols_to_update:
            return

        values.append(trade_id)
        sql = f"UPDATE trades SET {','.join(cols_to_update)} WHERE id=?"
        conn.execute(sql, values)
        conn.commit()
        logger.debug("Updated attribution on trade id=%d: %s", trade_id, list(attr_data.keys()))


def fetch_open_trades() -> list[Trade]:
    with _db_conn("fetch_open_trades") as conn:
        rows = conn.execute(
            "SELECT id,ts_open,ts_close,market_slug,market_id,side,qty,entry_px,"
            "exit_px,pnl_usd,fees_usd,reason_open,reason_close,confidence,mode,status,source "
            "FROM trades WHERE status='open' ORDER BY id ASC"
        ).fetchall()
    return [_row_to_trade(r) for r in rows]


def fetch_recent_closed(n: int = 20) -> list[Trade]:
    with _db_conn("fetch_recent_closed") as conn:
        rows = conn.execute(
            "SELECT id,ts_open,ts_close,market_slug,market_id,side,qty,entry_px,"
            "exit_px,pnl_usd,fees_usd,reason_open,reason_close,confidence,mode,status,source "
            "FROM trades WHERE status='closed' ORDER BY id DESC LIMIT ?",
            (n,),
        ).fetchall()
    return [_row_to_trade(r) for r in rows]


def rolling_stats(last_n: int) -> dict[str, Any]:
    with _db_conn("rolling_stats") as conn:
        rows = conn.execute(
            "SELECT pnl_usd FROM trades WHERE status='closed' ORDER BY id DESC LIMIT ?",
            (last_n,),
        ).fetchall()

    vals = [float(r[0] or 0.0) for r in rows]
    wins = sum(1 for v in vals if v > 0)
    losses = sum(1 for v in vals if v < 0)
    breakeven = sum(1 for v in vals if abs(v) < 1e-9)
    denom = wins + losses
    win_rate = (wins / denom * 100.0) if denom > 0 else 0.0
    total_pnl = sum(vals)
    avg_win = (sum(v for v in vals if v > 0) / wins) if wins > 0 else 0.0
    avg_loss = (sum(v for v in vals if v < 0) / losses) if losses > 0 else 0.0
    expectancy = (win_rate / 100.0 * avg_win) + ((1 - win_rate / 100.0) * avg_loss) if denom > 0 else 0.0

    return {
        "n": len(vals),
        "wins": wins,
        "losses": losses,
        "breakeven": breakeven,
        "win_rate": round(win_rate, 2),
        "pnl": round(total_pnl, 4),
        "avg_win": round(avg_win, 4),
        "avg_loss": round(avg_loss, 4),
        "expectancy": round(expectancy, 4),
    }


def total_realized_pnl() -> float:
    with _db_conn("total_pnl") as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(pnl_usd),0) FROM trades WHERE status='closed'"
        ).fetchone()
    return float(row[0] or 0.0)


def total_trade_count() -> int:
    with _db_conn("count") as conn:
        row = conn.execute("SELECT COUNT(*) FROM trades").fetchone()
    return int(row[0] or 0)


def _row_to_trade(r: tuple) -> Trade:
    return Trade(
        id=r[0],
        ts_open=r[1] or "",
        ts_close=r[2],
        market_slug=r[3] or "",
        market_id=r[4] or "",
        side=r[5] or "",
        qty=float(r[6] or 0),
        entry_px=float(r[7] or 0),
        exit_px=float(r[8]) if r[8] is not None else None,
        pnl_usd=float(r[9]) if r[9] is not None else None,
        fees_usd=float(r[10]) if r[10] is not None else None,
        reason_open=r[11],
        reason_close=r[12],
        confidence=float(r[13] or 0),
        mode=r[14] or "neutral",
        status=r[15] or "open",
        source=(r[16] or "bot") if len(r) > 16 else "bot",
    )
