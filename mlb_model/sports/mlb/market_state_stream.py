"""
sports/mlb/market_state_stream.py — Polymarket market state for candidate games

Thin wrapper that fetches order book data for a specific token pair.
Designed for integration with the existing sports_bot_v2 CLOB infrastructure.

In Phase 1 (shadow mode) this module is used READ-ONLY to compute:
    - ask_yes / ask_no
    - spread
    - depth
    - p_cost_yes / p_cost_no (market implied probability including fees)

In Phase 3 (merged execution), the existing bot's CLOB module takes over execution.
This module remains the READ path for the recommendation engine.

Public API:
    get_market_state(yes_token_id, no_token_id) -> MarketState | None
    compute_executable_cost(ask: float) -> float
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

CLOB_API_URL = os.getenv("CLOB_API_URL", "https://clob.polymarket.com")
GAMMA_API_URL = os.getenv("GAMMA_API_URL", "https://gamma-api.polymarket.com")

# Execution friction assumptions (from spec)
FEE_COST = float(os.getenv("FEE_COST", "0.02"))
SLIPPAGE_COST_BASE = float(os.getenv("SLIPPAGE_COST", "0.003"))

_CACHE: dict[str, tuple[float, "MarketState"]] = {}
BOOK_CACHE_TTL = float(os.getenv("BOOK_MAX_AGE_SEC", "5"))


@dataclass
class MarketState:
    yes_token_id: str
    no_token_id: str
    bid_yes: float | None
    ask_yes: float | None
    bid_no: float | None
    ask_no: float | None
    spread_yes: float | None
    spread_no: float | None
    depth_yes_usd: float
    depth_no_usd: float
    fetched_at: float = field(default_factory=time.monotonic)

    @property
    def age_seconds(self) -> float:
        return time.monotonic() - self.fetched_at

    @property
    def spread(self) -> float | None:
        return self.spread_yes

    @property
    def thin_side_depth(self) -> float:
        return min(self.depth_yes_usd, self.depth_no_usd)

    def executable_cost_yes(self) -> float:
        """P(cost to buy YES) = ask_yes + fee + slippage"""
        if self.ask_yes is None:
            return 1.0
        spread = self.spread_yes or 0.0
        slippage = max(SLIPPAGE_COST_BASE, spread * 0.35)
        return self.ask_yes + FEE_COST + slippage

    def executable_cost_no(self) -> float:
        """P(cost to buy NO) = ask_no + fee + slippage"""
        if self.ask_no is None:
            return 1.0
        spread = self.spread_no or 0.0
        slippage = max(SLIPPAGE_COST_BASE, spread * 0.35)
        return self.ask_no + FEE_COST + slippage


def _http_get_json(url: str, timeout: int = 8) -> Any:
    import urllib.request, json
    req = urllib.request.Request(url, headers={"User-Agent": "mlb_model/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _parse_book(book_data: dict, token_id: str) -> tuple[float | None, float | None, float]:
    """Extract best bid, ask, and top-5 depth from CLOB book response."""
    bids = sorted(book_data.get("bids") or [], key=lambda x: -float(x.get("price", 0)))
    asks = sorted(book_data.get("asks") or [], key=lambda x: float(x.get("price", 1)))

    best_bid = float(bids[0]["price"]) if bids else None
    best_ask = float(asks[0]["price"]) if asks else None

    # Compute top-5 depth (USD value)
    top5_depth = sum(
        float(lvl.get("size", 0)) * float(lvl.get("price", 0))
        for lvl in asks[:5]
    )
    return best_bid, best_ask, top5_depth


def get_market_state(yes_token_id: str, no_token_id: str) -> "MarketState | None":
    """
    Fetch current order book state for a YES/NO token pair.
    Returns None if fetch fails or books are empty.
    """
    cache_key = f"{yes_token_id}|{no_token_id}"
    cached = _CACHE.get(cache_key)
    if cached:
        ts, state = cached
        if time.monotonic() - ts < BOOK_CACHE_TTL:
            return state

    try:
        # Fetch YES book
        yes_url = f"{CLOB_API_URL}/book?token_id={yes_token_id}"
        yes_book = _http_get_json(yes_url)
        bid_yes, ask_yes, depth_yes = _parse_book(yes_book, yes_token_id)

        # Fetch NO book
        no_url = f"{CLOB_API_URL}/book?token_id={no_token_id}"
        no_book = _http_get_json(no_url)
        bid_no, ask_no, depth_no = _parse_book(no_book, no_token_id)

        spread_yes = (ask_yes - bid_yes) if (ask_yes is not None and bid_yes is not None) else None
        spread_no = (ask_no - bid_no) if (ask_no is not None and bid_no is not None) else None

        state = MarketState(
            yes_token_id=yes_token_id,
            no_token_id=no_token_id,
            bid_yes=bid_yes,
            ask_yes=ask_yes,
            bid_no=bid_no,
            ask_no=ask_no,
            spread_yes=spread_yes,
            spread_no=spread_no,
            depth_yes_usd=depth_yes,
            depth_no_usd=depth_no,
        )

        _CACHE[cache_key] = (time.monotonic(), state)
        return state

    except Exception as e:
        logger.debug("Market state fetch failed for %s: %s", yes_token_id[:16], e)
        return None


def compute_edge(p_model: float, market: "MarketState") -> dict[str, float]:
    """
    Compute YES and NO edge from model probability and market costs.
    Returns dict with edge_yes, edge_no, p_cost_yes, p_cost_no.
    """
    p_cost_yes = market.executable_cost_yes()
    p_cost_no = market.executable_cost_no()
    edge_yes = p_model - p_cost_yes
    edge_no = (1.0 - p_model) - p_cost_no
    return {
        "edge_yes": round(edge_yes, 6),
        "edge_no": round(edge_no, 6),
        "p_cost_yes": round(p_cost_yes, 6),
        "p_cost_no": round(p_cost_no, 6),
        "ask_yes": market.ask_yes,
        "ask_no": market.ask_no,
    }
