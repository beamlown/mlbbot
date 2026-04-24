"""Centralized ESPN MLB scoreboard + detail cache with background poll thread."""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request
from typing import Any

logger = logging.getLogger("core.espn_cache")

ESPN_SB_URL = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"
ESPN_DETAIL_URL = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/summary?event={}"

_lock = threading.Lock()
_scoreboard: dict[str, Any] = {"games": [], "fetched_at": None, "error": None}
_detail: dict[str, dict] = {}
_poll_thread: threading.Thread | None = None
_stop = threading.Event()


def _http_get(url: str, timeout: int = 8) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "dugout-dash/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _build_games_from_raw(raw: dict) -> list[dict]:
    games: list[dict] = []
    for event in raw.get("events", []):
        espn_id = str(event.get("id", ""))
        comp = (event.get("competitions") or [{}])[0]
        competitors = comp.get("competitors") or []
        home = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away = next((c for c in competitors if c.get("homeAway") == "away"), {})
        status_obj = comp.get("status") or {}
        status_type = status_obj.get("type") or {}
        sb_sit = comp.get("situation") or {}
        games.append({
            "espn_id": espn_id,
            "home": (home.get("team") or {}).get("displayName", "?"),
            "away": (away.get("team") or {}).get("displayName", "?"),
            "home_abbr": (home.get("team") or {}).get("abbreviation", ""),
            "away_abbr": (away.get("team") or {}).get("abbreviation", ""),
            "home_score": int(home.get("score", 0) or 0),
            "away_score": int(away.get("score", 0) or 0),
            "inning": int(status_obj.get("period") or 0),
            "inning_half": "bottom" if sb_sit.get("isTopInning") is False else "top",
            "status": status_type.get("name", "STATUS_UNKNOWN"),
            "status_display": status_type.get("shortDetail", ""),
            "outs": sb_sit.get("outs"),
            "balls": sb_sit.get("balls"),
            "strikes": sb_sit.get("strikes"),
            "on_first": bool(sb_sit.get("onFirst")),
            "on_second": bool(sb_sit.get("onSecond")),
            "on_third": bool(sb_sit.get("onThird")),
        })
    return games


def get_scoreboard() -> dict:
    with _lock:
        return dict(_scoreboard)


def get_detail(espn_id: str) -> dict | None:
    with _lock:
        return _detail.get(espn_id)


def _refresh_scoreboard() -> None:
    try:
        raw = _http_get(ESPN_SB_URL)
        games = _build_games_from_raw(raw)
        with _lock:
            _scoreboard["games"] = games
            _scoreboard["fetched_at"] = time.time()
            _scoreboard["error"] = None
    except Exception as e:
        with _lock:
            _scoreboard["error"] = str(e)
        logger.warning("espn scoreboard fetch failed: %s", e)


def _refresh_detail(espn_id: str) -> None:
    try:
        raw = _http_get(ESPN_DETAIL_URL.format(espn_id))
        with _lock:
            _detail[espn_id] = {"data": raw, "fetched_at": time.time()}
    except Exception as e:
        logger.warning("espn detail fetch failed (%s): %s", espn_id, e)


def _poll_loop() -> None:
    while not _stop.is_set():
        _refresh_scoreboard()
        with _lock:
            ids = [g["espn_id"] for g in _scoreboard["games"] if g["espn_id"]]
        for gid in ids[:15]:
            if _stop.is_set():
                break
            _refresh_detail(gid)
        _stop.wait(20.0)


def start() -> None:
    global _poll_thread
    if _poll_thread and _poll_thread.is_alive():
        return
    _stop.clear()
    _poll_thread = threading.Thread(target=_poll_loop, name="espn-cache", daemon=True)
    _poll_thread.start()
    logger.info("espn_cache poll thread started")


def stop() -> None:
    _stop.set()
