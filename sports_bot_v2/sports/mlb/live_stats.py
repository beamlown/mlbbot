"""
sports/mlb/live_stats.py — Live MLB game state from ESPN public API + MLB Stats API
Returns GameState with baseball-specific fields populated.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

from core.types import GameState
from core.utils import http_get_json, now_iso, retry_with_backoff
from sports.mlb.player_stats import enrich_game_state

logger = logging.getLogger("sports.mlb.live_stats")

ESPN_SCOREBOARD = "http://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"
ESPN_SUMMARY = "http://site.api.espn.com/apis/site/v2/sports/baseball/mlb/summary"
MLB_API_BASE = "https://statsapi.mlb.com/api/v1"

_GAME_CACHE: dict[str, tuple[float, GameState]] = {}
_SCOREBOARD_CACHE: tuple[float, list[dict]] | None = None

GAME_CACHE_TTL = 15.0       # MLB games update less frequently than basketball
SCOREBOARD_CACHE_TTL = 10.0

# MLB team name aliases for Polymarket question matching
# Keys: all common references (abbrevs, nicknames, city-only, Polymarket phrasing)
# Values: canonical full name matching ESPN display format
_MLB_ALIASES: dict[str, str] = {
    # ── Abbreviations ────────────────────────────────────────────────────────
    "nyy": "new york yankees",
    "nymets": "new york mets",
    "ny mets": "new york mets",
    "ny yankees": "new york yankees",
    "bos": "boston red sox",
    "lad": "los angeles dodgers",
    "laa": "los angeles angels",
    "la angels": "los angeles angels",
    "la dodgers": "los angeles dodgers",
    "chc": "chicago cubs",
    "cws": "chicago white sox",
    "chi cubs": "chicago cubs",
    "chi sox": "chicago white sox",
    "sf": "san francisco giants",
    "sd": "san diego padres",
    "oak": "oakland athletics",
    "sea": "seattle mariners",
    "tex": "texas rangers",
    "hou": "houston astros",
    "atl": "atlanta braves",
    "mia": "miami marlins",
    "phi": "philadelphia phillies",
    "pit": "pittsburgh pirates",
    "stl": "st. louis cardinals",
    "mil": "milwaukee brewers",
    "min": "minnesota twins",
    "det": "detroit tigers",
    "cle": "cleveland guardians",
    "kc": "kansas city royals",
    "tor": "toronto blue jays",
    "bal": "baltimore orioles",
    "tb": "tampa bay rays",
    "wsh": "washington nationals",
    "col": "colorado rockies",
    "ari": "arizona diamondbacks",
    "cin": "cincinnati reds",
    # ── Nickname-only (what Polymarket questions use) ─────────────────────────
    "yankees": "new york yankees",
    "mets": "new york mets",
    "red sox": "boston red sox",
    "dodgers": "los angeles dodgers",
    "angels": "los angeles angels",
    "cubs": "chicago cubs",
    "white sox": "chicago white sox",
    "giants": "san francisco giants",
    "padres": "san diego padres",
    "athletics": "oakland athletics",
    "as": "oakland athletics",       # "A's" → apostrophe stripped → "as"
    "mariners": "seattle mariners",
    "rangers": "texas rangers",
    "astros": "houston astros",
    "braves": "atlanta braves",
    "marlins": "miami marlins",
    "phillies": "philadelphia phillies",
    "pirates": "pittsburgh pirates",
    "cardinals": "st. louis cardinals",
    "brewers": "milwaukee brewers",
    "twins": "minnesota twins",
    "tigers": "detroit tigers",
    "guardians": "cleveland guardians",
    "royals": "kansas city royals",
    "blue jays": "toronto blue jays",
    "orioles": "baltimore orioles",
    "rays": "tampa bay rays",
    "nationals": "washington nationals",
    "rockies": "colorado rockies",
    "diamondbacks": "arizona diamondbacks",
    "dbacks": "arizona diamondbacks",
    "reds": "cincinnati reds",
}


def normalize_team_name(name: str) -> str:
    # Strip apostrophes first (so "A's" → "as"), then remove other punctuation
    n = name.lower().replace("'", "").replace("\u2019", "")
    n = re.sub(r"[^\w\s]", "", n).strip()
    n = re.sub(r"\s+", " ", n)
    return _MLB_ALIASES.get(n, n)


def _teams_match(a: str, b: str) -> bool:
    na, nb = normalize_team_name(a), normalize_team_name(b)
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    return False


def _detect_phase(inning: int, status_type: str) -> str:
    st = status_type.lower()
    if "final" in st or "game over" in st:
        return "FINAL"
    if inning == 0 or "pre" in st or "scheduled" in st or "warmup" in st:
        return "PRE_GAME"
    if inning <= 3:
        return "EARLY_INNINGS"
    if inning <= 6:
        return "MID_GAME"
    if inning <= 9:
        return "LATE_GAME"
    return "EXTRAS"


def _parse_runners(situation: dict) -> str:
    """Parse base runner situation into a compact string."""
    runners = []
    if situation.get("onFirst"):
        runners.append("1B")
    if situation.get("onSecond"):
        runners.append("2B")
    if situation.get("onThird"):
        runners.append("3B")
    if len(runners) == 3:
        return "loaded"
    return ",".join(runners)


def _parse_scoring_run(plays: list[dict]) -> tuple[str, int]:
    """Detect consecutive runs by one team in recent plays."""
    if not plays:
        return "", 0

    run_team = ""
    run_runs = 0

    for play in reversed(plays[-20:]):
        text = (play.get("text") or "").lower()
        scoring_team = play.get("team", {}).get("displayName") or ""
        runs = 0

        # Look for run-scoring plays
        for pat in [r"(\d+)\s+run", r"scores", r"home run", r"rbi"]:
            m = re.search(pat, text)
            if m:
                runs = int(m.group(1)) if m.lastindex else 1
                break

        if runs == 0:
            continue

        if not run_team:
            run_team = scoring_team
            run_runs = runs
        elif _teams_match(run_team, scoring_team):
            run_runs += runs
        else:
            break

    if run_runs < 3:
        return "", 0
    return run_team, run_runs


def _parse_pitcher_from_boxscore(boxscore: dict, home_id: str, away_id: str) -> tuple[str, int, str, int]:
    """Extract current pitcher and pitch count for home and away."""
    home_pitcher = away_pitcher = ""
    home_pitches = away_pitches = 0

    try:
        teams = boxscore.get("teams") or {}
        for side, team_id in [("home", home_id), ("away", away_id)]:
            team_data = teams.get(side) or {}
            pitchers = team_data.get("pitchers") or []
            # Last pitcher in list = current pitcher
            if pitchers:
                player_id = str(pitchers[-1])
                players = team_data.get("players") or {}
                player_key = f"ID{player_id}"
                player = players.get(player_key) or {}
                person = player.get("person") or {}
                name = person.get("fullName") or ""
                stats = (player.get("stats") or {}).get("pitching") or {}
                pitches = int(stats.get("numberOfPitches") or stats.get("pitchesThrown") or 0)
                if side == "home":
                    home_pitcher = name
                    home_pitches = pitches
                else:
                    away_pitcher = name
                    away_pitches = pitches
    except Exception as e:
        logger.debug("Pitcher parse error: %s", e)

    return home_pitcher, home_pitches, away_pitcher, away_pitches


def _fetch_scoreboard() -> list[dict]:
    global _SCOREBOARD_CACHE
    if _SCOREBOARD_CACHE:
        ts, data = _SCOREBOARD_CACHE
        if time.time() - ts < SCOREBOARD_CACHE_TTL:
            return data

    raw = retry_with_backoff(lambda: http_get_json(ESPN_SCOREBOARD, timeout=10), retries=2, backoff_ms=500)
    events = raw.get("events") or []
    _SCOREBOARD_CACHE = (time.time(), events)
    return events


def _fetch_game_summary(espn_event_id: str) -> dict[str, Any]:
    url = f"{ESPN_SUMMARY}?event={espn_event_id}"
    return retry_with_backoff(lambda: http_get_json(url, timeout=12), retries=2, backoff_ms=600)


def _unknown_state(home: str = "", away: str = "", espn_id: str = "") -> GameState:
    return GameState(
        home_team=home, away_team=away,
        home_score=0, away_score=0,
        period=0, clock="",
        status="unknown",
        scoring_run_team="", scoring_run_pts=0,
        last_5min_diff=0, halftime_adj=0.0,
        espn_event_id=espn_id,
        fetched_at=now_iso(),
        sport="baseball",
    )


def get_game_state(home_team: str, away_team: str) -> GameState:
    """
    Fetch live MLB game state from ESPN. Populates baseball-specific fields.
    Returns GameState(status="unknown") on failure.
    """
    cache_key = f"{normalize_team_name(home_team)}|{normalize_team_name(away_team)}"
    cached = _GAME_CACHE.get(cache_key)
    if cached:
        ts, state = cached
        if time.time() - ts < GAME_CACHE_TTL:
            return state

    try:
        events = _fetch_scoreboard()
    except Exception as e:
        logger.debug("ESPN MLB scoreboard fetch failed: %s", e)
        return _unknown_state(home_team, away_team)

    matched_event: dict | None = None
    for event in events:
        competitors = []
        try:
            competitors = event["competitions"][0]["competitors"]
        except (KeyError, IndexError):
            continue

        team_names = [c.get("team", {}).get("displayName", "") for c in competitors]
        if len(team_names) == 2 and (
            (_teams_match(team_names[0], home_team) or _teams_match(team_names[1], home_team)) and
            (_teams_match(team_names[0], away_team) or _teams_match(team_names[1], away_team))
        ):
            matched_event = event
            break

    if not matched_event:
        logger.debug("No ESPN MLB match for %s vs %s", home_team, away_team)
        return _unknown_state(home_team, away_team)

    espn_event_id = str(matched_event.get("id", ""))

    try:
        comp = matched_event["competitions"][0]
        competitors = comp["competitors"]

        home_comp = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away_comp = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

        home_name = home_comp.get("team", {}).get("displayName", home_team)
        away_name = away_comp.get("team", {}).get("displayName", away_team)
        home_id = str((home_comp.get("team") or {}).get("id") or "")
        away_id = str((away_comp.get("team") or {}).get("id") or "")
        home_score = int(home_comp.get("score", 0) or 0)
        away_score = int(away_comp.get("score", 0) or 0)

        # Baseball-specific status parsing
        status_obj = comp.get("status") or {}
        status_type = str((status_obj.get("type") or {}).get("name") or "")
        period = int(status_obj.get("period") or 0)   # ESPN uses period = inning number

        # Try to get inning from status detail
        inning = period
        inning_half = "top"
        outs = 0
        balls = 0
        strikes = 0
        runners_on = ""
        home_pitcher = away_pitcher = ""
        home_pitches = away_pitches = 0
        home_errors = away_errors = 0
        run_team = ""
        run_runs = 0

        phase = _detect_phase(inning, status_type)

        # Halftime-equivalent: big lead after 5 innings = weaker reversion signal
        halftime_adj = 0.0
        if inning >= 5:
            diff = home_score - away_score
            if abs(diff) >= 4:
                halftime_adj = -0.04 if diff < 0 else 0.02

        try:
            summary = _fetch_game_summary(espn_event_id)
            plays_data = summary.get("plays") or []

            # Situation (runners, outs, count)
            situation = summary.get("situation") or {}
            outs = int(situation.get("outs") or 0)
            balls = int(situation.get("balls") or 0)
            strikes = int(situation.get("strikes") or 0)
            runners_on = _parse_runners(situation)

            # Inning half from situation
            due_up = situation.get("dueUp") or {}
            inning_half_raw = str(situation.get("inningHalf") or "").lower()
            if "bot" in inning_half_raw:
                inning_half = "bottom"
            else:
                inning_half = "top"

            # Errors from linescore
            linescore = summary.get("linescore") or {}
            ls_teams = linescore.get("teams") or []
            for ls_team in ls_teams:
                team_data = ls_team.get("team") or {}
                tid = str(team_data.get("id") or "")
                errs = int(ls_team.get("errors") or 0)
                if tid == home_id:
                    home_errors = errs
                elif tid == away_id:
                    away_errors = errs

            # Pitcher data from boxscore
            boxscore = summary.get("boxscore") or {}
            home_pitcher, home_pitches, away_pitcher, away_pitches = _parse_pitcher_from_boxscore(
                boxscore, home_id, away_id
            )

            # Scoring run
            run_team, run_runs = _parse_scoring_run(plays_data)

        except Exception as e:
            logger.debug("MLB summary parse failed: %s", e)

        state = GameState(
            home_team=home_name,
            away_team=away_name,
            home_score=home_score,
            away_score=away_score,
            period=inning,
            clock="",
            status=phase,
            scoring_run_team=run_team,
            scoring_run_pts=run_runs,
            last_5min_diff=home_score - away_score,
            halftime_adj=halftime_adj,
            espn_event_id=espn_event_id,
            fetched_at=now_iso(),
            sport="baseball",
            # MLB fields
            inning=inning,
            inning_half=inning_half,
            outs=outs,
            balls=balls,
            strikes=strikes,
            runners_on=runners_on,
            home_pitcher=home_pitcher,
            away_pitcher=away_pitcher,
            home_pitcher_pitches=home_pitches,
            away_pitcher_pitches=away_pitches,
            home_errors=home_errors,
            away_errors=away_errors,
        )
        # Enrich with pitcher ERA-5 from MLB Stats API (cached 1hr; free, no auth)
        from datetime import datetime, timezone as _tz
        game_date = datetime.now(_tz.utc).strftime("%Y-%m-%d")
        enrich_game_state(state, game_date)

        _GAME_CACHE[cache_key] = (time.time(), state)
        return state

    except Exception as e:
        logger.warning("Error parsing ESPN MLB event %s: %s", espn_event_id, e)
        return _unknown_state(home_team, away_team, espn_event_id)


def extract_teams_from_question(question: str) -> tuple[str, str]:
    """Parse home vs away team from a Polymarket MLB question string."""
    q = question.strip()
    patterns = [
        r"(?i)will\s+(?:the\s+)?(.+?)\s+beat\s+(?:the\s+)?(.+?)\??$",
        r"(?i)(.+?)\s+vs\.?\s+(.+?)\??$",
        r"(?i)(.+?)\s+at\s+(?:the\s+)?(.+?)\??$",
        r"(?i)(?:the\s+)?(.+?)\s+@\s+(?:the\s+)?(.+?)\??$",
    ]
    for pat in patterns:
        m = re.search(pat, q)
        if m:
            a = m.group(1).strip()
            b = m.group(2).strip()
            if a and b and a.lower() != b.lower():
                return a, b
    return "", ""
