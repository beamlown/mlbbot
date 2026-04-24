"""hof_sql — seeded in-memory DB, each query returns expected shape."""
import sqlite3

import pytest


def _seed_db(path):
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE trades (
            id INTEGER PRIMARY KEY, ts_open TEXT, ts_close TEXT,
            market_slug TEXT, market_id TEXT, side TEXT, qty REAL,
            entry_px REAL, exit_px REAL, pnl_usd REAL, fees_usd REAL,
            reason_open TEXT, reason_close TEXT, confidence REAL,
            mode TEXT, status TEXT, sport TEXT
        )""")
    rows = [
        ("yankees-win", "BUY_YES", 0.50, 0.60, 10.00, "TAKE_PROFIT", "2026-04-16 18:00:00", "2026-04-16 20:00:00"),
        ("yankees-win", "BUY_YES", 0.55, 0.40, -15.00, "STOP_LOSS",   "2026-04-17 18:00:00", "2026-04-17 19:30:00"),
        ("red-sox-win", "BUY_YES", 0.48, 0.70, 22.00, "TAKE_PROFIT", "2026-04-17 19:00:00", "2026-04-17 22:00:00"),
        ("red-sox-win", "BUY_YES", 0.50, 0.55,  5.00, "TAKE_PROFIT", "2026-04-18 18:00:00", "2026-04-18 19:00:00"),
    ]
    for i, r in enumerate(rows, 1):
        conn.execute(
            "INSERT INTO trades (id, market_slug, side, entry_px, exit_px, pnl_usd, reason_close, ts_open, ts_close, status)"
            " VALUES (?,?,?,?,?,?,?,?,?,'closed')",
            (i, *r),
        )
    conn.commit()
    conn.close()


def _team_from_slug(slug: str) -> str:
    return slug.split("-win")[0]


def test_batting_avg(tmp_path):
    db = tmp_path / "t.db"
    _seed_db(db)
    import dugout_dash.hof_sql as hof
    hof.reset_cache()
    assert hof.batting_avg(db_path=str(db)) == pytest.approx(3/4)


def test_slugging_era(tmp_path):
    db = tmp_path / "t.db"
    _seed_db(db)
    import dugout_dash.hof_sql as hof
    hof.reset_cache()
    assert hof.slugging(db_path=str(db)) == pytest.approx((10+22+5)/3)
    assert hof.era(db_path=str(db)) == pytest.approx(-15.0)


def test_mvp_day(tmp_path):
    db = tmp_path / "t.db"
    _seed_db(db)
    import dugout_dash.hof_sql as hof
    hof.reset_cache()
    mvp = hof.mvp_day(db_path=str(db))
    # 2026-04-16=10, 2026-04-17 net=7, 2026-04-18=5 → 2026-04-16 wins
    assert mvp is not None
    assert mvp["day"] == "2026-04-16"
    assert mvp["pnl"] == pytest.approx(10.0)


def test_team_records(tmp_path):
    db = tmp_path / "t.db"
    _seed_db(db)
    import dugout_dash.hof_sql as hof
    hof.reset_cache()
    records = hof.team_records(db_path=str(db), team_from_slug=_team_from_slug)
    by_team = {r["team"]: r for r in records}
    assert by_team["yankees"]["wins"] == 1 and by_team["yankees"]["losses"] == 1
    assert by_team["red-sox"]["wins"] == 2 and by_team["red-sox"]["losses"] == 0
    assert by_team["red-sox"]["pnl"] == pytest.approx(27.0)
