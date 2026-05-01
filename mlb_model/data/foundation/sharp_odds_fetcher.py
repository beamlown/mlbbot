"""
data/foundation/sharp_odds_fetcher.py

Fetch Pinnacle MLB moneylines from the-odds-api.com, devig, write to
data/features/sharp_odds_history.parquet (append-only).

API docs: https://the-odds-api.com/liveapi/guides/v4/
Endpoint: GET /v4/sports/baseball_mlb/odds?apiKey=KEY&regions=us&markets=h2h&bookmakers=pinnacle&oddsFormat=decimal
"""
from __future__ import annotations
import json
import logging
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

ODDS_API_BASE = "https://api.the-odds-api.com/v4"
OUTPUT_PATH = Path("data/features/sharp_odds_history.parquet")


class SharpOddsError(Exception):
    pass


def _http_get_json(url: str) -> list:
    req = urllib.request.Request(url, headers={"User-Agent": "mlb_model/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _devig(home_dec: float, away_dec: float) -> tuple[float, float]:
    raw_home = 1.0 / home_dec
    raw_away = 1.0 / away_dec
    total = raw_home + raw_away
    return raw_home / total, raw_away / total


def parse_response(events: list, fetched_at: datetime) -> list[dict]:
    """Convert the-odds-api response to flat rows with devigged home_prob."""
    out = []
    for ev in events:
        home_team = ev.get("home_team")
        away_team = ev.get("away_team")
        commence = ev.get("commence_time")
        if not (home_team and away_team and commence):
            continue
        pinnacle = next((b for b in ev.get("bookmakers", []) if b.get("key") == "pinnacle"), None)
        if pinnacle is None:
            continue
        h2h = next((m for m in pinnacle.get("markets", []) if m.get("key") == "h2h"), None)
        if h2h is None:
            continue
        outcomes = {o.get("name"): o.get("price") for o in h2h.get("outcomes", [])}
        if home_team not in outcomes or away_team not in outcomes:
            continue
        home_prob, away_prob = _devig(outcomes[home_team], outcomes[away_team])
        out.append({
            "event_id": ev.get("id"),
            "fetched_at": fetched_at,
            "commence_time": commence,
            "home_team": home_team,
            "away_team": away_team,
            "home_dec": float(outcomes[home_team]),
            "away_dec": float(outcomes[away_team]),
            "home_prob": float(home_prob),
            "away_prob": float(away_prob),
        })
    return out


def fetch_pinnacle_mlb_moneylines(api_key: str | None = None) -> list[dict]:
    api_key = api_key or os.getenv("ODDS_API_KEY", "")
    if not api_key:
        raise SharpOddsError("ODDS_API_KEY not set")
    url = (f"{ODDS_API_BASE}/sports/baseball_mlb/odds"
           f"?apiKey={api_key}&regions=us&markets=h2h"
           f"&bookmakers=pinnacle&oddsFormat=decimal")
    try:
        data = _http_get_json(url)
    except Exception as e:
        raise SharpOddsError(f"odds-api fetch failed: {e}") from e
    return parse_response(data, fetched_at=datetime.now(timezone.utc))


def snapshot() -> int:
    """Fetch + append to sharp_odds_history.parquet. Returns # rows added."""
    rows = fetch_pinnacle_mlb_moneylines()
    if not rows:
        logger.info("snapshot: 0 rows fetched")
        return 0
    df = pd.DataFrame(rows)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT_PATH.exists():
        existing = pd.read_parquet(OUTPUT_PATH)
        df = pd.concat([existing, df], ignore_index=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    logger.info("snapshot: appended %d rows; total now %d", len(rows), len(df))
    return len(rows)
