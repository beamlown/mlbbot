"""
sports/mlb/mlb_game_pk_resolver.py

Resolve MLB Stats API `game_pk` from (home_abbrev, away_abbrev, date).

Needed because ESPN and MLB Stats API use different game ID systems.
Our live game state comes from ESPN (with ESPN event_id), but lineup_live,
pitcher_quality, and batter_quality all need MLB Stats API IDs (MLBAM).

Uses https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=YYYY-MM-DD
Caches per-date (1h TTL) to minimize API hits.
"""
from __future__ import annotations
import json
import logging
import time
import urllib.request
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)

_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date}&hydrate=team"
_CACHE: dict[str, tuple[float, list[dict]]] = {}  # date_iso -> (timestamp, games)
_CACHE_TTL_SEC = 3600.0

# ESPN/Statcast team abbrev -> MLB Stats API abbrev (where they differ)
# MLB Stats API uses the "teamCode" field. Most are identical.
_TEAM_ABBREV_TO_MLB = {
    "KCR": "KC",
    "TBR": "TB",
    "SDP": "SD",
    "SFG": "SF",
    "CHW": "CWS",
    "WSH": "WSH",
    "AZ":  "ARI",
    "ATH": "OAK",
}


def _mlb_abbrev(team: str) -> str:
    return _TEAM_ABBREV_TO_MLB.get(team.upper(), team.upper())


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "mlb_model/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def _fetch_schedule(target: date) -> list[dict]:
    key = target.isoformat()
    now = time.monotonic()
    cached = _CACHE.get(key)
    if cached is not None and (now - cached[0]) < _CACHE_TTL_SEC:
        return cached[1]
    url = _SCHEDULE_URL.format(date=key)
    try:
        data = _http_get_json(url)
    except Exception as e:
        logger.warning("MLB schedule fetch failed for %s: %s", key, e)
        return []
    games: list[dict] = []
    for day in data.get("dates", []):
        for g in day.get("games", []):
            try:
                pk = int(g.get("gamePk"))
            except Exception:
                continue
            teams = g.get("teams") or {}
            h = ((teams.get("home") or {}).get("team") or {})
            a = ((teams.get("away") or {}).get("team") or {})
            games.append({
                "game_pk": pk,
                "home_abbrev": str(h.get("abbreviation", "")).upper(),
                "away_abbrev": str(a.get("abbreviation", "")).upper(),
            })
    _CACHE[key] = (now, games)
    return games


def resolve_game_pk(home_team: str, away_team: str, target: date) -> Optional[int]:
    """Return MLB Stats API game_pk for today's home vs away matchup. None if not found."""
    h = _mlb_abbrev(home_team)
    a = _mlb_abbrev(away_team)
    schedule = _fetch_schedule(target)
    for g in schedule:
        if g["home_abbrev"] == h and g["away_abbrev"] == a:
            return g["game_pk"]
    # Fallback: try team_code or partial match (Athletics, etc.)
    for g in schedule:
        if g["home_abbrev"].startswith(h[:3]) and g["away_abbrev"].startswith(a[:3]):
            return g["game_pk"]
    return None
