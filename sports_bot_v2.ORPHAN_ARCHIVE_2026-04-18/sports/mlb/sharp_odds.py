"""
sports/mlb/sharp_odds.py — Pinnacle devigged moneyline probability via the-odds-api.com

Public API: get_sharp_prob(home_team, away_team) -> float | None
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

from core.utils import atomic_write_json, http_get_json, retry_with_backoff

logger = logging.getLogger("sports.mlb.sharp_odds")

_ODDS_API_URL = (
    "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"
    "?apiKey={key}&regions=us&bookmakers=pinnacle&markets=h2h&oddsFormat=decimal"
)

# Module-level cache
_cache_data: list[dict[str, Any]] = []
_cache_ts: float = 0.0


def _match(query: str, candidate: str) -> bool:
    q, c = query.lower(), candidate.lower()
    return q in c or c in q


def _devig(home_dec: float, away_dec: float) -> float:
    p_h = 1.0 / home_dec
    p_a = 1.0 / away_dec
    return p_h / (p_h + p_a)


def _budget_path() -> str:
    return os.getenv("ODDS_BUDGET_PATH", "runtime/odds_budget.json")


def _load_budget() -> dict[str, Any]:
    path = _budget_path()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("budget file must be object")
            data.setdefault("date", "")
            data.setdefault("count", 0)
            data.setdefault("month", "")
            data.setdefault("month_count", 0)
            data.setdefault("mode", "normal")
            return data
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return {"date": "", "count": 0, "month": "", "month_count": 0, "mode": "normal"}


def _save_budget(data: dict[str, Any]) -> None:
    atomic_write_json(_budget_path(), data)


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _month_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _budget_mode(month_count: int) -> str:
    monthly_soft = int(os.getenv("MAX_ODDS_CALLS_PER_MONTH_TARGET", "18000"))
    monthly_hard = int(os.getenv("MAX_ODDS_CALLS_PER_MONTH_HARD", "20000"))
    if month_count >= monthly_hard:
        return "hard_stop"
    if month_count >= monthly_soft:
        return "soft_throttle"
    return "normal"


def _check_and_increment_budget() -> bool:
    """Returns True if call is allowed, False if budget exhausted. Increments on True."""
    max_calls = int(os.getenv("MAX_ODDS_CALLS_PER_DAY", "600"))
    budget = _load_budget()
    today = _today_utc()
    month = _month_utc()

    if budget.get("month") != month:
        budget["month"] = month
        budget["month_count"] = 0
        budget["mode"] = "normal"

    if budget.get("date") != today:
        budget["date"] = today
        budget["count"] = 0

    budget["mode"] = _budget_mode(int(budget.get("month_count", 0)))

    if budget["count"] >= max_calls:
        logger.warning(
            "odds_budget: daily limit %d reached (count=%d)", max_calls, budget["count"]
        )
        global _cache_data, _cache_ts
        if not _cache_ts:
            _cache_ts = time.time()
        _save_budget(budget)
        return False

    if budget["mode"] == "hard_stop":
        logger.warning(
            "odds_budget: monthly hard cap reached (month_count=%d)", budget.get("month_count", 0)
        )
        _save_budget(budget)
        return False

    if budget["mode"] == "soft_throttle":
        throttle_mod = int(os.getenv("ODDS_SOFT_THROTTLE_MOD", "3"))
        next_count = int(budget.get("count", 0)) + 1
        if throttle_mod > 1 and (next_count % throttle_mod) != 0:
            logger.info(
                "odds_budget: soft throttle active (month_count=%d, skipping non-essential fetch)",
                budget.get("month_count", 0),
            )
            _save_budget(budget)
            return False

    budget["count"] += 1
    budget["month_count"] = int(budget.get("month_count", 0)) + 1
    budget["mode"] = _budget_mode(int(budget.get("month_count", 0)))
    _save_budget(budget)
    return True


def _fetch_odds() -> list[dict[str, Any]]:
    """Fetch raw game list from the-odds-api. May raise on error."""
    key = os.getenv("ODDS_API_KEY", "")
    if not key:
        raise ValueError("ODDS_API_KEY not set")
    url = _ODDS_API_URL.format(key=key)
    return retry_with_backoff(lambda: http_get_json(url))  # type: ignore[return-value]


def _get_cached_odds() -> list[dict[str, Any]] | None:
    """Return cached data if still fresh, else None."""
    global _cache_data, _cache_ts
    ttl = float(os.getenv("ODDS_CACHE_TTL_SECONDS", "90"))
    if _cache_ts and (time.time() - _cache_ts) < ttl:
        return _cache_data
    return None


def get_sharp_prob(home_team: str, away_team: str) -> float | None:
    """
    Return Pinnacle devigged P(home wins) for the given matchup, or None on any failure.

    Uses a module-level cache (TTL controlled by ODDS_CACHE_TTL_SECONDS).
    Budget is tracked in ODDS_BUDGET_PATH; resets daily.
    Disabled entirely when ODDS_API_KEY is not set.
    """
    global _cache_data, _cache_ts

    if not os.getenv("ODDS_API_KEY", ""):
        return None

    try:
        data = _get_cached_odds()
        if data is None:
            if not _check_and_increment_budget():
                return None
            data = _fetch_odds()
            _cache_data = data
            _cache_ts = time.time()
            logger.debug("sharp_odds: fetched %d games from Pinnacle", len(data))

        for game in data:
            odds_home = game.get("home_team", "")
            odds_away = game.get("away_team", "")
            if not (_match(home_team, odds_home) and _match(away_team, odds_away)):
                continue

            # Find the Pinnacle h2h market
            for bm in game.get("bookmakers", []):
                if bm.get("key") != "pinnacle":
                    continue
                for mkt in bm.get("markets", []):
                    if mkt.get("key") != "h2h":
                        continue
                    outcomes = {o["name"]: o["price"] for o in mkt.get("outcomes", [])}
                    home_dec = outcomes.get(odds_home)
                    away_dec = outcomes.get(odds_away)
                    if home_dec and away_dec and home_dec > 1.0 and away_dec > 1.0:
                        prob = _devig(home_dec, away_dec)
                        logger.debug(
                            "sharp_odds: %s vs %s → home_dec=%.3f away_dec=%.3f prob=%.4f",
                            odds_home, odds_away, home_dec, away_dec, prob,
                        )
                        return prob

        logger.debug(
            "sharp_odds: no Pinnacle match for home=%r away=%r", home_team, away_team
        )
        return None

    except Exception as exc:
        logger.warning("sharp_odds: error fetching odds — %s", exc)
        return None
