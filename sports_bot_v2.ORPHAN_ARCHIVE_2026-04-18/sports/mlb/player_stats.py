"""
sports/mlb/player_stats.py — MLB Stats API integration (free, no auth required)
Fetches starting pitcher recent form and team batting trends.
Results are cached in memory and attached to GameState via enrich_game_state().
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from core.utils import http_get_json, retry_with_backoff

logger = logging.getLogger("sports.mlb.player_stats")

MLB_API_BASE = os.getenv("MLB_STATS_API_BASE", "https://statsapi.mlb.com/api/v1")

# In-memory caches
_pitcher_cache: dict[str, tuple[float, dict]] = {}    # key=pitcher_id, value=(ts, profile)
_schedule_cache: tuple[float, list[dict]] | None = None
_batting_cache: dict[str, tuple[float, dict]] = {}    # key=team_id, value=(ts, stats)

PITCHER_CACHE_TTL = 3600.0   # 1 hour — pitcher stats don't change mid-game
SCHEDULE_CACHE_TTL = 300.0   # 5 min — probable starters updated infrequently
BATTING_CACHE_TTL = 3600.0   # 1 hour


def _fetch(path: str, params: str = "") -> Any:
    url = f"{MLB_API_BASE}{path}"
    if params:
        url += ("&" if "?" in url else "?") + params
    return retry_with_backoff(lambda: http_get_json(url, timeout=12), retries=2, backoff_ms=500)


def _fetch_probable_pitchers(game_date: str) -> list[dict]:
    """Returns list of game dicts with probablePitcher hydrated."""
    global _schedule_cache
    if _schedule_cache:
        ts, data = _schedule_cache
        if time.time() - ts < SCHEDULE_CACHE_TTL:
            return data

    try:
        data = _fetch(
            f"/schedule?sportId=1&date={game_date}&hydrate=probablePitcher(note),team,linescore"
        )
        games = []
        for date_entry in (data.get("dates") or []):
            games.extend(date_entry.get("games") or [])
        _schedule_cache = (time.time(), games)
        return games
    except Exception as e:
        logger.debug("MLB schedule fetch failed: %s", e)
        return []


def _fetch_pitcher_game_log(pitcher_id: str) -> list[dict]:
    """Fetch last 5 starts from pitcher game log. Falls back to prior season if current has no data."""
    cached = _pitcher_cache.get(pitcher_id)
    if cached:
        ts, profile = cached
        if time.time() - ts < PITCHER_CACHE_TTL:
            return profile.get("game_log", [])

    from datetime import datetime, timezone
    current_year = datetime.now(timezone.utc).year

    for season in [current_year, current_year - 1]:
        try:
            data = _fetch(f"/people/{pitcher_id}/stats?stats=gameLog&group=pitching&season={season}&limit=5")
            splits = []
            for stat_group in (data.get("stats") or []):
                splits = stat_group.get("splits") or []
                if splits:
                    break
            if splits:
                return splits
        except Exception as e:
            logger.debug("Pitcher game log fetch failed id=%s season=%s: %s", pitcher_id, season, e)

    return []


def _compute_pitcher_profile(pitcher_id: str, pitcher_name: str) -> dict:
    """Compute ERA, avg innings, HR rate from last 5 starts."""
    game_log = _fetch_pitcher_game_log(pitcher_id)

    if not game_log:
        return {
            "name": pitcher_name,
            "era5": 4.50,   # league average fallback
            "avg_innings": 5.0,
            "hr_rate": 1.0,
            "is_rested": True,
        }

    total_er = 0.0
    total_ip = 0.0
    total_hr = 0
    starts = 0

    for split in game_log[-5:]:
        stats = split.get("stat") or {}
        ip_str = str(stats.get("inningsPitched") or "0.0")
        try:
            # Convert 6.1 IP → 6.333 actual innings
            parts = ip_str.split(".")
            ip = float(parts[0]) + (float(parts[1]) / 3.0 if len(parts) > 1 else 0.0)
        except Exception:
            ip = 0.0

        er = float(stats.get("earnedRuns") or 0)
        hr = int(stats.get("homeRunsAllowed") or stats.get("homeRuns") or 0)

        total_er += er
        total_ip += ip
        total_hr += hr
        starts += 1

    era5 = (total_er / total_ip * 9.0) if total_ip > 0 else 4.50
    avg_innings = total_ip / starts if starts > 0 else 5.0
    hr_rate = total_hr / starts if starts > 0 else 1.0

    # Is rested: check if last start was 4+ days ago
    is_rested = True
    if game_log:
        last_start = game_log[-1].get("date") or ""
        if last_start:
            try:
                from datetime import datetime, timezone, timedelta
                last_dt = datetime.fromisoformat(last_start)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                days_rest = (datetime.now(timezone.utc) - last_dt).days
                is_rested = days_rest >= 4
            except Exception:
                pass

    profile = {
        "name": pitcher_name,
        "era5": round(era5, 2),
        "avg_innings": round(avg_innings, 1),
        "hr_rate": round(hr_rate, 2),
        "is_rested": is_rested,
    }
    _pitcher_cache[pitcher_id] = (time.time(), {"game_log": game_log, **profile})
    return profile


def _fetch_team_batting(team_id: str) -> dict:
    """Fetch team batting stats (season to date, used as proxy for form)."""
    cached = _batting_cache.get(team_id)
    if cached:
        ts, stats = cached
        if time.time() - ts < BATTING_CACHE_TTL:
            return stats

    try:
        data = _fetch(f"/teams/{team_id}/stats?stats=season&group=hitting&season=2026")
        for stat_group in (data.get("stats") or []):
            splits = stat_group.get("splits") or []
            if splits:
                stat = splits[0].get("stat") or {}
                ops_str = str(stat.get("ops") or "0.700")
                try:
                    ops = float(ops_str)
                except Exception:
                    ops = 0.700
                result = {"ops": ops, "team_id": team_id}
                _batting_cache[team_id] = (time.time(), result)
                return result
    except Exception as e:
        logger.debug("Team batting fetch failed id=%s: %s", team_id, e)

    return {"ops": 0.700, "team_id": team_id}


def get_probable_pitchers(home_team_name: str, away_team_name: str, game_date: str) -> tuple[dict, dict]:
    """
    Look up probable pitchers for a game and return enrichment profiles.
    Returns (home_pitcher_profile, away_pitcher_profile).
    Each profile has: name, era5, avg_innings, hr_rate, is_rested.
    """
    games = _fetch_probable_pitchers(game_date)

    home_profile = {"name": "unknown", "era5": 4.50, "avg_innings": 5.0, "hr_rate": 1.0, "is_rested": True}
    away_profile = {"name": "unknown", "era5": 4.50, "avg_innings": 5.0, "hr_rate": 1.0, "is_rested": True}

    def _name_match(a: str, b: str) -> bool:
        a, b = a.lower().strip(), b.lower().strip()
        return a in b or b in a or any(tok in b for tok in a.split() if len(tok) > 3)

    for game in games:
        teams = game.get("teams") or {}
        home_data = teams.get("home") or {}
        away_data = teams.get("away") or {}
        home_name = (home_data.get("team") or {}).get("name") or ""
        away_name = (away_data.get("team") or {}).get("name") or ""

        if not (_name_match(home_team_name, home_name) or _name_match(away_team_name, away_name)):
            continue

        # Home pitcher
        home_pp = home_data.get("probablePitcher") or {}
        if home_pp:
            pid = str(home_pp.get("id") or "")
            pname = str(home_pp.get("fullName") or home_pp.get("name") or "")
            if pid:
                home_profile = _compute_pitcher_profile(pid, pname)

        # Away pitcher
        away_pp = away_data.get("probablePitcher") or {}
        if away_pp:
            pid = str(away_pp.get("id") or "")
            pname = str(away_pp.get("fullName") or away_pp.get("name") or "")
            if pid:
                away_profile = _compute_pitcher_profile(pid, pname)

        break  # Found the game

    return home_profile, away_profile


def enrich_game_state(gs, game_date: str) -> None:
    """
    Fetch pitcher profiles and team batting, write into gs in-place.
    Called once per new market discovery; cached heavily.
    gs must be a GameState with sport=="baseball".
    """
    try:
        home_profile, away_profile = get_probable_pitchers(gs.home_team, gs.away_team, game_date)
        gs.home_pitcher_era5 = home_profile.get("era5", 4.50)
        gs.away_pitcher_era5 = away_profile.get("era5", 4.50)
        if not gs.home_pitcher:
            gs.home_pitcher = home_profile.get("name", "")
        if not gs.away_pitcher:
            gs.away_pitcher = away_profile.get("name", "")
        logger.debug(
            "Enriched %s vs %s: home_ERA5=%.2f away_ERA5=%.2f",
            gs.home_team, gs.away_team, gs.home_pitcher_era5, gs.away_pitcher_era5
        )
    except Exception as e:
        logger.debug("Enrichment failed for %s vs %s: %s", gs.home_team, gs.away_team, e)
