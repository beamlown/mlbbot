"""
sports/ncaab/live_stats.py — Live NCAAB game state from ESPN public API
Ported from march_madness_bot mm_live_stats.py.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

from core.types import GameState
from core.utils import http_get_json, now_iso, retry_with_backoff

logger = logging.getLogger("sports.ncaab.live_stats")

ESPN_SCOREBOARD = (
    "http://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"
)
ESPN_SUMMARY = (
    "http://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary"
)

_GAME_CACHE: dict[str, tuple[float, GameState]] = {}
_SCOREBOARD_CACHE: tuple[float, list[dict]] | None = None

GAME_CACHE_TTL = 2.0
SCOREBOARD_CACHE_TTL = 5.0

_NCAAB_ALIASES: dict[str, str] = {
    "unc": "north carolina",
    "uconn": "connecticut",
    "ucf": "central florida",
    "unlv": "nevada las vegas",
    "vcu": "virginia commonwealth",
    "lsu": "louisiana state",
    "smu": "southern methodist",
    "tcu": "texas christian",
    "byu": "brigham young",
    "ole miss": "mississippi",
    "pitt": "pittsburgh",
    "usc": "southern california",
    "miami fl": "miami",
    "miami oh": "miami ohio",
    "a&m": "texas a&m",
    "st. john's": "st johns",
    "saint john's": "st johns",
    "n.c. state": "nc state",
    "nc state": "north carolina state",
}


def normalize_team_name(name: str) -> str:
    n = re.sub(r"[^\w\s]", "", name.lower()).strip()
    n = re.sub(r"\s+", " ", n)
    return _NCAAB_ALIASES.get(n, n)


def _teams_match(a: str, b: str) -> bool:
    na, nb = normalize_team_name(a), normalize_team_name(b)
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    return False


def _detect_phase(period: int, clock: str, status_type: str) -> str:
    st = status_type.lower()
    if "final" in st:
        return "FINAL"
    if "halftime" in st or "half" in st:
        return "HALFTIME"
    if period == 0 or "pre" in st or "scheduled" in st:
        return "PRE_GAME"
    if period == 1:
        return "FIRST_HALF"
    if period == 2:
        return "SECOND_HALF"
    if period > 2:
        return "OVERTIME"
    return "unknown"


def _parse_scoring_run(plays: list[dict]) -> tuple[str, int]:
    if not plays:
        return "", 0

    run_team = ""
    run_pts = 0

    for play in reversed(plays[-30:]):
        scoring_team = play.get("team", {}).get("displayName") or ""
        pts = 0
        text = (play.get("text") or "").lower()

        for pat in [r"(\d+)-point", r"(\d+) pt", r"makes (\d+)"]:
            m = re.search(pat, text)
            if m:
                pts = int(m.group(1))
                break
        if pts == 0 and ("free throw" in text or "foul shot" in text):
            pts = 1
        if pts == 0 and "three" in text:
            pts = 3
        if pts == 0 and ("layup" in text or "dunk" in text or "jumper" in text or "makes" in text):
            pts = 2

        if pts == 0:
            continue

        if not run_team:
            run_team = scoring_team
            run_pts = pts
        elif _teams_match(run_team, scoring_team):
            run_pts += pts
        else:
            break

    if run_pts < 4:
        return "", 0
    return run_team, run_pts


def _parse_team_fouls(summary: dict, home_id: str, away_id: str) -> tuple[int, int]:
    home_fouls = away_fouls = 0
    try:
        teams = (summary.get("boxscore") or {}).get("teams") or []
        for td in teams:
            tid = str((td.get("team") or {}).get("id") or "")
            for stat in (td.get("statistics") or []):
                sname = (stat.get("name") or "").lower()
                if sname in ("fouls", "pf", "teamfouls", "team fouls", "personalfouls"):
                    val_str = str(stat.get("displayValue") or stat.get("value") or "0")
                    try:
                        val = int(float(val_str))
                    except ValueError:
                        val = 0
                    if tid == home_id:
                        home_fouls = val
                    elif tid == away_id:
                        away_fouls = val
                    break
    except Exception:
        pass
    return home_fouls, away_fouls


def _parse_game_situation(
    summary: dict, plays: list[dict], home_id: str, away_id: str
) -> tuple[str, int, int, str, bool, str]:
    possession = ""
    home_to = away_to = -1
    last_play = ""
    is_timeout = False
    in_bonus = ""

    try:
        situation = summary.get("situation") or {}

        ht_raw = situation.get("homeTimeouts")
        at_raw = situation.get("awayTimeouts")
        if ht_raw is not None:
            home_to = int(ht_raw)
        if at_raw is not None:
            away_to = int(at_raw)

        poss_id = str(situation.get("possession") or "")
        if poss_id == home_id:
            possession = "home"
        elif poss_id == away_id:
            possession = "away"

        last_play_obj = situation.get("lastPlay") or {}
        last_play = str(last_play_obj.get("text") or "")
        if not last_play and plays:
            last_play = str(plays[-1].get("text") or "")

        if plays:
            last_type = ((plays[-1].get("type") or {}).get("text") or "").lower()
            last_txt = (plays[-1].get("text") or "").lower()
            if "timeout" in last_type or last_txt.startswith("timeout") or "calls timeout" in last_txt:
                is_timeout = True

        home_bonus = bool(situation.get("homeTeamInBonus") or situation.get("homeInBonus") or False)
        away_bonus = bool(situation.get("awayTeamInBonus") or situation.get("awayInBonus") or False)
        if home_bonus and away_bonus:
            in_bonus = "both"
        elif home_bonus:
            in_bonus = "home"
        elif away_bonus:
            in_bonus = "away"

    except Exception:
        pass

    return possession, home_to, away_to, last_play, is_timeout, in_bonus


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
        sport="basketball",
    )


def get_game_state(home_team: str, away_team: str) -> GameState:
    cache_key = f"{normalize_team_name(home_team)}|{normalize_team_name(away_team)}"
    cached = _GAME_CACHE.get(cache_key)
    if cached:
        ts, state = cached
        if time.time() - ts < GAME_CACHE_TTL:
            return state

    try:
        events = _fetch_scoreboard()
    except Exception as e:
        logger.debug("ESPN scoreboard fetch failed: %s", e)
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
        logger.debug("No ESPN match for %s vs %s", home_team, away_team)
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

        status_obj = comp.get("status") or {}
        period = int(status_obj.get("period") or 0)
        clock = str(status_obj.get("displayClock") or "")
        status_type = str((status_obj.get("type") or {}).get("name") or "")
        phase = _detect_phase(period, clock, status_type)

        halftime_adj = 0.0
        if phase in ("SECOND_HALF", "FINAL"):
            diff = home_score - away_score
            if abs(diff) >= 10:
                halftime_adj = -0.05 if diff < 0 else 0.03

        run_team = ""
        run_pts = 0
        home_fouls = away_fouls = 0
        home_to = away_to = -1
        possession = last_play = in_bonus = ""
        is_timeout = False
        try:
            summary = _fetch_game_summary(espn_event_id)
            plays_data = summary.get("plays") or []
            run_team, run_pts = _parse_scoring_run(plays_data)
            home_fouls, away_fouls = _parse_team_fouls(summary, home_id, away_id)
            possession, home_to, away_to, last_play, is_timeout, in_bonus = _parse_game_situation(
                summary, plays_data, home_id, away_id
            )
        except Exception as e:
            logger.debug("Play-by-play/detail fetch failed: %s", e)

        state = GameState(
            home_team=home_name,
            away_team=away_name,
            home_score=home_score,
            away_score=away_score,
            period=period,
            clock=clock,
            status=phase,
            scoring_run_team=run_team,
            scoring_run_pts=run_pts,
            last_5min_diff=home_score - away_score,
            halftime_adj=halftime_adj,
            espn_event_id=espn_event_id,
            fetched_at=now_iso(),
            sport="basketball",
            home_fouls=home_fouls,
            away_fouls=away_fouls,
            home_timeouts=home_to,
            away_timeouts=away_to,
            possession=possession,
            last_play=last_play,
            is_timeout=is_timeout,
            in_bonus=in_bonus,
        )
        _GAME_CACHE[cache_key] = (time.time(), state)
        return state

    except Exception as e:
        logger.warning("Error parsing ESPN event %s: %s", espn_event_id, e)
        return _unknown_state(home_team, away_team, espn_event_id)


def extract_teams_from_question(question: str) -> tuple[str, str]:
    q = question.strip()
    patterns = [
        r"(?i)will\s+(.+?)\s+beat\s+(?:the\s+)?(.+?)\??$",
        r"(?i)(.+?)\s+vs\.?\s+(.+?)\??$",
        r"(?i)(.+?)\s+at\s+(.+?)\??$",
    ]
    for pat in patterns:
        m = re.search(pat, q)
        if m:
            a = m.group(1).strip()
            b = m.group(2).strip()
            if a and b and a.lower() != b.lower():
                return a, b
    return "", ""
