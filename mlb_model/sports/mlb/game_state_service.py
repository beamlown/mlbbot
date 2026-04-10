"""
sports/mlb/game_state_service.py — Detailed live MLB game state

Fetches granular in-game state needed for model inference:
  score, inning, half, outs, base runners, pitcher IDs, pitch counts

Data sources:
  - ESPN summary API (primary, no auth needed)
  - Backed by live_game_registry for game discovery

The GameStateSnapshot returned here maps 1:1 to the model's feature set.
Cache TTL: GAME_STATE_CACHE_TTL seconds (default 8s after first-step live cadence tuning).

Public API:
    get_game_snapshot(home_team, away_team) -> GameStateSnapshot | None
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from sports.mlb.team_normalizer import normalize

logger = logging.getLogger(__name__)

ESPN_SUMMARY = "http://site.api.espn.com/apis/site/v2/sports/baseball/mlb/summary"
GAME_STATE_CACHE_TTL = float(os.getenv("GAME_STATE_CACHE_TTL", "8"))

_CACHE: dict[str, tuple[float, "GameStateSnapshot"]] = {}


@dataclass
class GameStateSnapshot:
    """Live game state exactly as needed for model feature engineering."""
    # Identity
    game_id: str                  # ESPN event ID
    home_team: str                # canonical abbreviation
    away_team: str
    date: str                     # YYYY-MM-DD
    # Score state
    home_score: int
    away_score: int
    score_diff: int               # home_score - away_score
    # Time state
    inning: int                   # 1-9+
    inning_half: int              # 0=top, 1=bottom
    outs: int                     # 0-2
    # Base runners
    base_state: int               # 0-7 encoding
    # Game phase
    status: str                   # EARLY_INNINGS | MID_GAME | LATE_GAME | EXTRAS | FINAL | PRE_GAME
    game_progress: float          # outs_elapsed / 54, capped 1.0
    outs_elapsed: int
    # Pitchers
    home_pitcher_id: int          # pitcher on mound for home team (pitcher this half-inning)
    away_pitcher_id: int
    home_pitch_count: int         # pitches thrown this game by current home pitcher
    away_pitch_count: int
    home_is_bullpen: bool
    away_is_bullpen: bool
    home_tto: float               # times through order proxy
    away_tto: float
    # Timestamps
    fetched_at: float = field(default_factory=time.monotonic)
    espn_fetched_at: str = ""

    @property
    def is_live(self) -> bool:
        return self.status in {"EARLY_INNINGS", "MID_GAME", "LATE_GAME", "EXTRAS"}

    @property
    def age_seconds(self) -> float:
        return time.monotonic() - self.fetched_at


def _http_get_json(url: str, timeout: int = 12) -> Any:
    import urllib.request, json
    req = urllib.request.Request(url, headers={"User-Agent": "mlb_model/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _base_state(situation: dict) -> int:
    b1 = 1 if situation.get("onFirst") else 0
    b2 = 2 if situation.get("onSecond") else 0
    b3 = 4 if situation.get("onThird") else 0
    return b1 + b2 + b3


def _outs_elapsed(inning: int, half: int, outs: int) -> int:
    completed = (inning - 1) * 2 + half
    return completed * 3 + outs


def _parse_pitcher_info(boxscore: dict, home_id: str, away_id: str) -> dict:
    """
    Extract current pitcher IDs, starter IDs, and pitch counts from ESPN boxscore.

    ESPN's pitchers list is ordered by appearance: pitchers[0] = starter,
    pitchers[-1] = current pitcher on mound.
    is_bullpen is True when the current pitcher is not the game starter.
    """
    result = {
        "home_pitcher_id": -1, "away_pitcher_id": -1,
        "home_starter_id": -1, "away_starter_id": -1,
        "home_pitch_count": 0, "away_pitch_count": 0,
        "home_is_bullpen": False, "away_is_bullpen": False,
    }
    try:
        teams = boxscore.get("teams") or {}
        for side, team_id, prefix in [("home", home_id, "home"), ("away", away_id, "away")]:
            team_data = teams.get(side) or {}
            pitchers = team_data.get("pitchers") or []
            if pitchers:
                starter_id = int(pitchers[0])
                current_id = int(pitchers[-1])
                players = team_data.get("players") or {}
                player_key = f"ID{current_id}"
                player = players.get(player_key) or {}
                stats = (player.get("stats") or {}).get("pitching") or {}
                pitches = int(stats.get("numberOfPitches") or stats.get("pitchesThrown") or 0)
                result[f"{prefix}_pitcher_id"] = current_id
                result[f"{prefix}_starter_id"] = starter_id
                result[f"{prefix}_pitch_count"] = pitches
                result[f"{prefix}_is_bullpen"] = (current_id != starter_id)
    except Exception as e:
        logger.debug("Pitcher parse error: %s", e)
    return result


def _detect_phase(inning: int, status_name: str) -> str:
    st = status_name.lower()
    if "final" in st or "post" in st:
        return "FINAL"
    if inning == 0 or "pre" in st or "sched" in st:
        return "PRE_GAME"
    if inning <= 3:
        return "EARLY_INNINGS"
    if inning <= 6:
        return "MID_GAME"
    if inning <= 9:
        return "LATE_GAME"
    return "EXTRAS"


def get_game_snapshot(home_team: str, away_team: str) -> "GameStateSnapshot | None":
    """
    Fetch detailed game state. Returns None if game not found or not started.
    Uses a short cache (GAME_STATE_CACHE_TTL seconds).
    """
    hn = normalize(home_team)
    an = normalize(away_team)
    # Include ESPN event ID in key so doubleheaders (same teams, same day)
    # do not share a cache slot. Resolved after registry lookup below.
    _prelim_key = f"{hn}|{an}"

    # Find game in registry first (needed for the event-ID-scoped cache key)
    from sports.mlb.live_game_registry import get_game_by_teams
    game_reg = get_game_by_teams(home_team, away_team)
    if not game_reg:
        logger.debug("Game not found in registry: %s vs %s", home_team, away_team)
        return None

    espn_event_id = game_reg.espn_event_id
    # Scope cache key by event ID to avoid doubleheader collisions
    cache_key = f"{hn}|{an}|{espn_event_id}"

    cached = _CACHE.get(cache_key)
    if cached:
        ts, snap = cached
        if time.monotonic() - ts < GAME_STATE_CACHE_TTL:
            return snap

    try:
        url = f"{ESPN_SUMMARY}?event={espn_event_id}"
        summary = _http_get_json(url)
    except Exception as e:
        logger.warning("ESPN summary fetch failed for event %s: %s", espn_event_id, e)
        return None

    try:
        # Competition metadata
        comps = summary.get("header", {}).get("competitions") or []
        comp_meta = comps[0] if comps else {}
        home_id = ""
        away_id = ""
        for c in comp_meta.get("competitors", []):
            if c.get("homeAway") == "home":
                home_id = str((c.get("team") or {}).get("id") or "")
            else:
                away_id = str((c.get("team") or {}).get("id") or "")

        # Status
        status_obj = comp_meta.get("status") or {}
        status_name = (status_obj.get("type") or {}).get("name") or ""
        inning = int(status_obj.get("period") or game_reg.inning)
        phase = _detect_phase(inning, status_name)

        # Situation (runners, outs, count)
        situation = summary.get("situation") or {}
        outs = int(situation.get("outs") or 0)
        bs = _base_state(situation)

        inning_half_raw = str(situation.get("inningHalf") or "").lower()
        inning_half = 1 if "bot" in inning_half_raw else 0

        # Scores from registry (faster than re-parsing)
        home_score = game_reg.home_score
        away_score = game_reg.away_score

        # Pitcher info from boxscore
        boxscore = summary.get("boxscore") or {}
        pitcher_info = _parse_pitcher_info(boxscore, home_id, away_id)

        home_pc = pitcher_info["home_pitch_count"]
        away_pc = pitcher_info["away_pitch_count"]

        # TTO: matches training formula exactly — starts at 1.0 on first batter,
        # increments by 1 per order faced, capped at 3.0.
        # Training uses (abs_faced / 9.0 + 1.0); 27 pitches ≈ 9 batters.
        home_tto = min(3.0, home_pc / 27.0 + 1.0) if home_pc > 0 else 1.0
        away_tto = min(3.0, away_pc / 27.0 + 1.0) if away_pc > 0 else 1.0

        # Bullpen flag: matches training — True when current pitcher is not the starter.
        # Determined from ESPN pitchers list (index 0 = starter, -1 = current).
        home_is_bullpen = pitcher_info["home_is_bullpen"]
        away_is_bullpen = pitcher_info["away_is_bullpen"]

        outs_el = _outs_elapsed(inning, inning_half, outs)
        game_progress = min(1.0, outs_el / 54.0)

        snap = GameStateSnapshot(
            game_id=espn_event_id,
            home_team=hn,
            away_team=an,
            date=game_reg.date,
            home_score=home_score,
            away_score=away_score,
            score_diff=home_score - away_score,
            inning=inning,
            inning_half=inning_half,
            outs=outs,
            base_state=bs,
            status=phase,
            game_progress=game_progress,
            outs_elapsed=outs_el,
            home_pitcher_id=pitcher_info["home_pitcher_id"],
            away_pitcher_id=pitcher_info["away_pitcher_id"],
            home_pitch_count=home_pc,
            away_pitch_count=away_pc,
            home_is_bullpen=home_is_bullpen,
            away_is_bullpen=away_is_bullpen,
            home_tto=round(home_tto, 2),
            away_tto=round(away_tto, 2),
        )

        _CACHE[cache_key] = (time.monotonic(), snap)
        return snap

    except Exception as e:
        logger.warning("Error parsing game state for %s vs %s: %s", home_team, away_team, e)
        return None


def snapshot_age(home_team: str, away_team: str) -> float:
    """Return seconds since last successful snapshot fetch, or inf."""
    hn, an = normalize(home_team), normalize(away_team)
    # Search cache for any entry matching this team pair (any event ID)
    prefix = f"{hn}|{an}|"
    for key, (ts, _) in _CACHE.items():
        if key.startswith(prefix):
            return time.monotonic() - ts
    return float("inf")
