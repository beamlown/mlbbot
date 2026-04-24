"""Hall-of-Fame SQL queries. 60s in-memory cache keyed by (fn, db_path)."""
from __future__ import annotations

import sqlite3
import threading
import time
from typing import Any, Callable

from dugout_dash import config as cfg

_cache: dict[tuple, tuple[float, Any]] = {}
_lock = threading.Lock()


def reset_cache() -> None:
    with _lock:
        _cache.clear()


def _cached(fn_name: str, db_path: str, compute: Callable[[], Any]) -> Any:
    key = (fn_name, db_path)
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and (now - hit[0] < cfg.HOF_CACHE_TTL_SEC):
            return hit[1]
    try:
        val = compute()
    except sqlite3.Error:
        val = None
    with _lock:
        _cache[key] = (now, val)
    return val


def _conn(db_path: str) -> sqlite3.Connection:
    c = sqlite3.connect(db_path, timeout=2.0)
    c.row_factory = sqlite3.Row
    return c


def batting_avg(db_path: str | None = None) -> float | None:
    db_path = db_path or cfg.DB_PATH
    def _compute():
        with _conn(db_path) as c:
            row = c.execute(
                "SELECT SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END), COUNT(*) "
                "FROM trades WHERE status='closed'"
            ).fetchone()
            wins, total = (row[0] or 0), (row[1] or 0)
            return (wins / total) if total else None
    return _cached("batting_avg", db_path, _compute)


def slugging(db_path: str | None = None) -> float | None:
    db_path = db_path or cfg.DB_PATH
    def _compute():
        with _conn(db_path) as c:
            row = c.execute(
                "SELECT AVG(pnl_usd) FROM trades WHERE status='closed' AND pnl_usd > 0"
            ).fetchone()
            return row[0]
    return _cached("slugging", db_path, _compute)


def era(db_path: str | None = None) -> float | None:
    db_path = db_path or cfg.DB_PATH
    def _compute():
        with _conn(db_path) as c:
            row = c.execute(
                "SELECT AVG(pnl_usd) FROM trades WHERE status='closed' AND pnl_usd < 0"
            ).fetchone()
            return row[0]
    return _cached("era", db_path, _compute)


def mvp_day(db_path: str | None = None) -> dict | None:
    db_path = db_path or cfg.DB_PATH
    def _compute():
        with _conn(db_path) as c:
            row = c.execute(
                "SELECT DATE(ts_close) d, SUM(pnl_usd) p FROM trades"
                " WHERE status='closed' GROUP BY d ORDER BY p DESC LIMIT 1"
            ).fetchone()
            if not row or row["p"] is None:
                return None
            return {"day": row["d"], "pnl": row["p"]}
    return _cached("mvp_day", db_path, _compute)


def no_hitter(db_path: str | None = None) -> dict | None:
    db_path = db_path or cfg.DB_PATH
    def _compute():
        with _conn(db_path) as c:
            rows = c.execute(
                "SELECT DATE(ts_close) d, SUM(CASE WHEN pnl_usd>0 THEN 1 ELSE 0 END) w, COUNT(*) n "
                "FROM trades WHERE status='closed' GROUP BY d"
            ).fetchall()
        days = [r for r in rows if r["n"] > 0 and r["w"] == r["n"]]
        if not days:
            return None
        return {"count": len(days), "most_recent": max(r["d"] for r in days)}
    return _cached("no_hitter", db_path, _compute)


def _default_team_resolver() -> Callable[[str], str]:
    try:
        from sports.mlb.adapter import team_from_slug as _r
        return _r
    except Exception:
        return lambda s: (s or "").split("-")[0]


def team_records(
    db_path: str | None = None,
    team_from_slug: Callable[[str], str] | None = None,
) -> list[dict]:
    db_path = db_path or cfg.DB_PATH
    resolver = team_from_slug or _default_team_resolver()
    def _compute() -> list[dict]:
        with _conn(db_path) as c:
            rows = c.execute(
                "SELECT market_slug, pnl_usd FROM trades WHERE status='closed'"
            ).fetchall()
        agg: dict[str, dict] = {}
        for r in rows:
            team = resolver(r["market_slug"] or "")
            a = agg.setdefault(team, {"team": team, "wins": 0, "losses": 0, "pnl": 0.0, "trades": 0})
            pnl = r["pnl_usd"] or 0.0
            a["pnl"] += pnl
            a["trades"] += 1
            if pnl > 0: a["wins"] += 1
            elif pnl < 0: a["losses"] += 1
        out = list(agg.values())
        for a in out:
            a["batting_avg"] = (a["wins"] / a["trades"]) if a["trades"] else None
        out.sort(key=lambda x: x["pnl"], reverse=True)
        return out
    result = _cached("team_records", db_path, _compute)
    return result if result is not None else []


def dynasty(db_path: str | None = None, team_from_slug=None) -> dict | None:
    recs = team_records(db_path=db_path, team_from_slug=team_from_slug)
    return recs[0] if recs else None


def rookie_of_the_year(db_path: str | None = None, team_from_slug=None) -> dict | None:
    db_path = db_path or cfg.DB_PATH
    resolver = team_from_slug or _default_team_resolver()
    def _compute():
        with _conn(db_path) as c:
            rows = c.execute(
                "SELECT market_slug, ts_open, pnl_usd FROM trades WHERE status='closed'"
            ).fetchall()
        firsts: dict[str, str] = {}
        pnls: dict[str, float] = {}
        for r in rows:
            team = resolver(r["market_slug"] or "")
            ts = r["ts_open"]
            if team not in firsts or ts < firsts[team]:
                firsts[team] = ts
            pnls[team] = pnls.get(team, 0.0) + (r["pnl_usd"] or 0.0)
        profitable = [(t, firsts[t], pnls[t]) for t in firsts if pnls[t] > 0]
        if not profitable:
            return None
        profitable.sort(key=lambda x: x[1], reverse=True)
        t, first, pnl = profitable[0]
        return {"team": t, "first_trade": first, "pnl": pnl}
    return _cached("rookie_of_the_year", db_path, _compute)
