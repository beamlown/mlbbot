"""
sports/mlb/lineup_live.py — Live lineup + current batter/pitcher fetch from MLB Stats API.

Endpoint: https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live
"""
from __future__ import annotations
import json
import logging
import urllib.request
from dataclasses import dataclass, field
from typing import Optional
import time

logger = logging.getLogger(__name__)

MLB_LIVE_FEED = "https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
_CACHE: dict[int, tuple[float, "LineupSnapshot"]] = {}
_CACHE_TTL_SEC = 15.0


class LineupError(Exception):
    pass


@dataclass
class LineupSnapshot:
    current_batter_id: int
    current_pitcher_id: int
    current_batter_stand: str    # L / R / S
    current_pitcher_throws: str  # L / R
    current_lineup_position: int # 1-9
    home_lineup: list[int] = field(default_factory=list)
    away_lineup: list[int] = field(default_factory=list)
    # 2026-04-20: per-side pitcher IDs (MLBAM). Starter = first pitcher used; current = last.
    # Needed so pitcher_quality lookups can use MLBAM IDs instead of ESPN IDs.
    home_starter_id: int = 0
    away_starter_id: int = 0
    home_current_pitcher_id: int = 0
    away_current_pitcher_id: int = 0


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "mlb_model/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def parse_live_response(data: dict) -> Optional[LineupSnapshot]:
    """Extract the fields we need from the MLB Stats API live feed response."""
    try:
        live = data.get("liveData", {})
        ls = live.get("linescore", {})
        bs = live.get("boxscore", {})
        offense = ls.get("offense") or {}
        defense = ls.get("defense") or {}
        cur_batter = (offense.get("batter") or {}).get("id")
        cur_pitcher = (defense.get("pitcher") or {}).get("id")
        if cur_batter is None or cur_pitcher is None:
            return None

        order_str = offense.get("battingOrder")
        if order_str is None:
            return None
        cur_pos = int(order_str) + 1

        teams = bs.get("teams") or {}
        home_lineup = list(teams.get("home", {}).get("battingOrder") or [])
        away_lineup = list(teams.get("away", {}).get("battingOrder") or [])

        home_players = teams.get("home", {}).get("players") or {}
        away_players = teams.get("away", {}).get("players") or {}
        all_players = {**home_players, **away_players}
        batter_player = all_players.get(f"ID{cur_batter}", {})
        pitcher_player = all_players.get(f"ID{cur_pitcher}", {})
        batter_stand = (batter_player.get("batSide") or {}).get("code", "?")
        pitcher_throws = (pitcher_player.get("pitchHand") or {}).get("code", "?")

        # Per-side pitcher lists: pitchers[0] = starter, pitchers[-1] = current
        home_pitchers = list(teams.get("home", {}).get("pitchers") or [])
        away_pitchers = list(teams.get("away", {}).get("pitchers") or [])
        home_starter = int(home_pitchers[0]) if home_pitchers else 0
        away_starter = int(away_pitchers[0]) if away_pitchers else 0
        home_current = int(home_pitchers[-1]) if home_pitchers else 0
        away_current = int(away_pitchers[-1]) if away_pitchers else 0

        return LineupSnapshot(
            current_batter_id=int(cur_batter),
            current_pitcher_id=int(cur_pitcher),
            current_batter_stand=batter_stand,
            current_pitcher_throws=pitcher_throws,
            current_lineup_position=cur_pos,
            home_lineup=[int(x) for x in home_lineup],
            away_lineup=[int(x) for x in away_lineup],
            home_starter_id=home_starter,
            away_starter_id=away_starter,
            home_current_pitcher_id=home_current,
            away_current_pitcher_id=away_current,
        )
    except Exception as e:
        logger.warning("parse_live_response failed: %s", e)
        return None


def fetch_live_lineup(game_pk: int) -> LineupSnapshot:
    """Fetch + cache (15s TTL). Raises LineupError on network failure."""
    now = time.monotonic()
    cached = _CACHE.get(game_pk)
    if cached is not None and (now - cached[0]) < _CACHE_TTL_SEC:
        return cached[1]
    url = MLB_LIVE_FEED.format(game_pk=game_pk)
    try:
        data = _http_get_json(url)
    except Exception as e:
        raise LineupError(f"MLB Stats API fetch failed: {e}") from e
    snap = parse_live_response(data)
    if snap is None:
        raise LineupError(f"could not parse lineup for game_pk={game_pk}")
    _CACHE[game_pk] = (now, snap)
    return snap
