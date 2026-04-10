"""
sports/mlb/live_game_registry.py — Authoritative live MLB game registry

This is the single source of truth for "which games are live right now."
It does NOT infer game status from market prices — it reads ESPN's public
scoreboard API which reflects actual game state.

Public API:
    refresh_registry() -> list[LiveGame]
        Fetch current scoreboard and return all games.

    get_live_games() -> list[LiveGame]
        Return only games that are currently in progress.

    get_game(espn_event_id: str) -> LiveGame | None

Data source: ESPN public scoreboard (no API key required)
Cache TTL: SCOREBOARD_CACHE_TTL seconds (default 10s)

LiveGame fields:
    espn_event_id: str
    date: str (YYYY-MM-DD)
    home_team: str  (canonical abbreviation)
    away_team: str
    home_score: int
    away_score: int
    status: str     (PRE_GAME | EARLY_INNINGS | MID_GAME | LATE_GAME | EXTRAS | FINAL | unknown)
    inning: int
    inning_half: str  ("top" | "bottom" | "")
    outs: int
    is_live: bool
    fetched_at: float  (monotonic time of last fetch)
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from sports.mlb.team_normalizer import normalize

logger = logging.getLogger(__name__)

ESPN_SCOREBOARD = "http://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"

SCOREBOARD_CACHE_TTL = float(os.getenv("SCOREBOARD_CACHE_TTL", "10"))

LIVE_STATUSES = {"EARLY_INNINGS", "MID_GAME", "LATE_GAME", "EXTRAS"}

_registry: list["LiveGame"] = []
_registry_ts: float = 0.0
# Maps espn_event_id -> monotonic time when game first became live
_live_since: dict[str, float] = {}
# Maps espn_event_id -> last known status (for transition detection)
_last_status: dict[str, str] = {}

REGISTRY_STALE_WARN_SEC = float(os.getenv("REGISTRY_STALE_WARN_SEC", "60"))


@dataclass
class LiveGame:
    espn_event_id: str
    date: str
    home_team: str    # canonical abbreviation
    away_team: str
    home_team_display: str
    away_team_display: str
    home_score: int
    away_score: int
    status: str
    inning: int
    inning_half: str  # "top" | "bottom" | ""
    outs: int
    is_live: bool
    fetched_at: float = field(default_factory=time.monotonic)

    @property
    def game_key(self) -> str:
        return f"{self.away_team}@{self.home_team}:{self.date}"


def _http_get_json(url: str, timeout: int = 10) -> Any:
    import urllib.request
    import json
    req = urllib.request.Request(url, headers={"User-Agent": "mlb_model/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _detect_phase(inning: int, status_type_name: str) -> str:
    st = str(status_type_name).lower()
    if "final" in st or "game over" in st or "post" in st:
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


def _parse_event(event: dict) -> "LiveGame | None":
    try:
        comp = event["competitions"][0]
        competitors = comp["competitors"]
        home_comp = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away_comp = next((c for c in competitors if c.get("homeAway") == "away"), None)
        if not home_comp or not away_comp:
            return None

        home_display = home_comp.get("team", {}).get("displayName", "")
        away_display = away_comp.get("team", {}).get("displayName", "")
        home_abbrev = normalize(home_comp.get("team", {}).get("abbreviation", home_display))
        away_abbrev = normalize(away_comp.get("team", {}).get("abbreviation", away_display))

        home_score = int(home_comp.get("score") or 0)
        away_score = int(away_comp.get("score") or 0)

        status_obj = comp.get("status") or {}
        status_type = (status_obj.get("type") or {}).get("name") or ""
        inning = int(status_obj.get("period") or 0)
        phase = _detect_phase(inning, status_type)

        # Try to extract inning half from status display detail
        inning_half = ""
        status_detail = str(status_obj.get("type", {}).get("shortDetail") or "").lower()
        if "bot" in status_detail or "bottom" in status_detail:
            inning_half = "bottom"
        elif "top" in status_detail:
            inning_half = "top"
        elif status_detail and phase in LIVE_STATUSES:
            # Log unexpected shortDetail so fragile string parsing is visible
            logger.debug("Unrecognized inning_half in shortDetail: %r", status_detail)

        # Game date
        date_raw = event.get("date", "")[:10]  # YYYY-MM-DD

        return LiveGame(
            espn_event_id=str(event.get("id", "")),
            date=date_raw,
            home_team=home_abbrev,
            away_team=away_abbrev,
            home_team_display=home_display,
            away_team_display=away_display,
            home_score=home_score,
            away_score=away_score,
            status=phase,
            inning=inning,
            inning_half=inning_half,
            outs=0,  # detailed outs from game_state_service
            is_live=phase in LIVE_STATUSES,
            fetched_at=time.monotonic(),
        )
    except Exception as e:
        logger.debug("Error parsing ESPN event: %s", e)
        return None


def refresh_registry() -> list["LiveGame"]:
    """Fetch scoreboard and update module-level registry."""
    global _registry, _registry_ts, _live_since, _last_status

    try:
        raw = _http_get_json(ESPN_SCOREBOARD, timeout=10)
        events = raw.get("events") or []
        games = []
        now = time.monotonic()
        for event in events:
            g = _parse_event(event)
            if g:
                prev_status = _last_status.get(g.espn_event_id, "")
                # Record transition into live status
                if g.is_live and prev_status not in LIVE_STATUSES:
                    _live_since[g.espn_event_id] = now
                    logger.info("Game went live: %s @ %s (event %s)",
                                g.away_team, g.home_team, g.espn_event_id)
                _last_status[g.espn_event_id] = g.status
                games.append(g)
        _registry = games
        _registry_ts = now
        logger.debug("Registry refreshed: %d games (%d live)",
                     len(games), sum(1 for g in games if g.is_live))
        return games
    except Exception as e:
        age = registry_age_seconds()
        logger.warning("Failed to refresh game registry: %s (registry age: %.0fs)", e, age)
        if age > REGISTRY_STALE_WARN_SEC:
            logger.error(
                "Registry is stale (%.0fs old, threshold %.0fs) — live game status unreliable",
                age, REGISTRY_STALE_WARN_SEC,
            )
        return _registry  # return stale if available


def _maybe_refresh() -> list["LiveGame"]:
    if time.monotonic() - _registry_ts > SCOREBOARD_CACHE_TTL:
        return refresh_registry()
    return _registry


def get_live_games() -> list["LiveGame"]:
    """Return games currently in progress."""
    games = _maybe_refresh()
    return [g for g in games if g.is_live]


def get_all_games() -> list["LiveGame"]:
    """Return all games (pregame, live, final)."""
    return _maybe_refresh()


def get_game_by_teams(home_team: str, away_team: str) -> "LiveGame | None":
    """Find a game by team names (normalized)."""
    hn = normalize(home_team)
    an = normalize(away_team)
    games = _maybe_refresh()
    for g in games:
        if g.home_team == hn and g.away_team == an:
            return g
    return None


def get_game(espn_event_id: str) -> "LiveGame | None":
    """Find a game by ESPN event ID."""
    games = _maybe_refresh()
    for g in games:
        if g.espn_event_id == espn_event_id:
            return g
    return None


def registry_age_seconds() -> float:
    """Seconds since last successful registry refresh."""
    if _registry_ts == 0.0:
        return float("inf")
    return time.monotonic() - _registry_ts


def is_registry_stale() -> bool:
    """True if the registry has not been successfully refreshed recently."""
    return registry_age_seconds() > REGISTRY_STALE_WARN_SEC


def get_live_since(espn_event_id: str) -> float:
    """
    Seconds since the game with this ESPN event ID transitioned to live status.
    Returns float('inf') if the transition was never observed (e.g. process
    started mid-game). Callers should treat inf as 'unknown, assume warmed up'
    rather than 'never live'.
    """
    ts = _live_since.get(espn_event_id)
    if ts is None:
        return float("inf")
    return time.monotonic() - ts
