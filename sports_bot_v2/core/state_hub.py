from __future__ import annotations

import threading
import time
from typing import Any


class StateHub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._marks: dict[str, dict[str, Any]] = {}
        self._games: dict[str, dict[str, Any]] = {}

    def update_mark(
        self,
        *,
        market_slug: str,
        market_id: str,
        asset_id: str,
        current_price: float | None,
        best_bid: float | None,
        best_ask: float | None,
        spread: float | None,
        source: str = "polymarket_stream",
    ) -> None:
        with self._lock:
            self._marks[market_slug] = {
                "market_slug": market_slug,
                "market_id": market_id,
                "asset_id": asset_id,
                "current_price": current_price,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread": spread,
                "source_ts": time.time(),
                "stale": False,
                "source": source,
            }

    def update_game(
        self,
        *,
        market_slug: str,
        game_status: str | None,
        inning: int | None,
        inning_half: str | None,
        outs: int | None,
        home_score: int | None,
        away_score: int | None,
        game_source: str = "games_poll",
    ) -> None:
        with self._lock:
            self._games[market_slug] = {
                "market_slug": market_slug,
                "game_status": game_status,
                "inning": inning,
                "inning_half": inning_half,
                "outs": outs,
                "home_score": home_score,
                "away_score": away_score,
                "game_source_ts": time.time(),
                "game_stale": False,
                "game_source": game_source,
            }

    def snapshot(self, stale_after_sec: float = 15.0) -> dict[str, dict[str, Any]]:
        now = time.time()
        with self._lock:
            out = {}
            all_slugs = set(self._marks.keys()) | set(self._games.keys())
            for slug in all_slugs:
                row = dict(self._marks.get(slug, {}))
                if row:
                    row["stale"] = (now - float(row.get("source_ts") or 0)) > stale_after_sec
                game = dict(self._games.get(slug, {}))
                if game:
                    game["game_stale"] = (now - float(game.get("game_source_ts") or 0)) > stale_after_sec
                    row.update(game)
                out[slug] = row
            return out


GLOBAL_STATE_HUB = StateHub()
