"""
data/foundation/elo_daily_updater.py

Roll yesterday's MLB results into the existing elo_table.parquet.

Strategy: load existing table, fetch yesterday's completed games via ESPN scoreboard
(same source registry already uses), apply Elo update, write back.

Standard Elo with K=4 (low for MLB — single-game outcome is high variance).
Home-field advantage: 24 Elo points.
"""
from __future__ import annotations
import json
import logging
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)

ELO_TABLE_PATH = Path("data/features/elo_table.parquet")
DEFAULT_RATING = 1500.0
HFA = 24.0
K = 4.0
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"


def _expected_home(elo_home: float, elo_away: float) -> float:
    diff = (elo_home + HFA) - elo_away
    return 1.0 / (1.0 + 10.0 ** (-diff / 400.0))


def update_for_date(elo: dict[str, float], home: str, away: str,
                    home_won: bool) -> None:
    """Mutates elo dict in place."""
    elo_home = elo.get(home, DEFAULT_RATING)
    elo_away = elo.get(away, DEFAULT_RATING)
    expected = _expected_home(elo_home, elo_away)
    actual = 1.0 if home_won else 0.0
    delta = K * (actual - expected)
    elo[home] = elo_home + delta
    elo[away] = elo_away - delta


def _fetch_completed_games(target_date: date) -> list[dict]:
    """Return list of {home, away, home_score, away_score} for completed games on date."""
    url = f"{ESPN_SCOREBOARD}?dates={target_date.strftime('%Y%m%d')}"
    req = urllib.request.Request(url, headers={"User-Agent": "mlb_model/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    games = []
    for ev in data.get("events", []):
        comps = ev.get("competitions") or []
        if not comps:
            continue
        c = comps[0]
        status = (c.get("status") or {}).get("type", {}).get("name", "")
        if "FINAL" not in status.upper():
            continue
        teams = c.get("competitors") or []
        if len(teams) != 2:
            continue
        h = next((t for t in teams if t.get("homeAway") == "home"), None)
        a = next((t for t in teams if t.get("homeAway") == "away"), None)
        if h is None or a is None:
            continue
        games.append({
            "home": (h.get("team") or {}).get("abbreviation", ""),
            "away": (a.get("team") or {}).get("abbreviation", ""),
            "home_score": int(h.get("score", 0)),
            "away_score": int(a.get("score", 0)),
        })
    return games


def update_elo_through_yesterday(today: Optional[date] = None) -> int:
    """
    Load elo_table, fetch yesterday's results, apply updates, write back.
    Returns number of games processed.
    """
    today = today or date.today()
    yesterday = today - timedelta(days=1)

    if not ELO_TABLE_PATH.exists():
        raise FileNotFoundError(f"Elo table not found at {ELO_TABLE_PATH}; run pregame_prior_builder first")

    df = pd.read_parquet(ELO_TABLE_PATH)
    if "team" in df.columns and "rating" in df.columns:
        latest = df.sort_values("date").drop_duplicates("team", keep="last")
        elo = dict(zip(latest["team"], latest["rating"]))
    else:
        raise ValueError(f"Unexpected elo_table schema: {df.columns.tolist()}")

    games = _fetch_completed_games(yesterday)
    logger.info("Found %d completed games on %s", len(games), yesterday)
    for g in games:
        if not g["home"] or not g["away"]:
            continue
        update_for_date(elo, g["home"], g["away"], home_won=g["home_score"] > g["away_score"])

    new_rows = pd.DataFrame([
        {"team": team, "date": today, "rating": rating} for team, rating in elo.items()
    ])
    out = pd.concat([df, new_rows], ignore_index=True)
    out.to_parquet(ELO_TABLE_PATH, index=False)
    logger.info("Updated elo_table: +%d team rows for %s", len(new_rows), today)
    return len(games)


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    n = update_elo_through_yesterday()
    print(f"Processed {n} games")


if __name__ == "__main__":
    main()
