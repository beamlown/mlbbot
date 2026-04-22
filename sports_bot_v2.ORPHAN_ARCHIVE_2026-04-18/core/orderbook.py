"""
core/orderbook.py — Normalized orderbook snapshot from Polymarket Gamma API
100% sport-agnostic.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from core.types import Market, OBSnapshot
from core.utils import http_get_json, now_iso, retry_with_backoff

logger = logging.getLogger("core.orderbook")

GAMMA_MARKETS = "https://gamma-api.polymarket.com/markets"
GAMMA_OB = "https://gamma-api.polymarket.com/orderbook"
CLOB_BOOK = "https://clob.polymarket.com/book"

MAX_SPREAD: float = float(os.getenv("MAX_SPREAD", "0.04"))
MIN_DEPTH_TOP5_USD: float = float(os.getenv("MIN_DEPTH_TOP5_USD", "500"))


def _sum_depth(levels: list[dict], top_n: int = 5) -> float:
    total = 0.0
    for lvl in levels[:top_n]:
        try:
            px = float(lvl.get("price", 0) or 0)
            sz = float(lvl.get("size", 0) or 0)
            total += px * sz
        except Exception:
            pass
    return total


def _depth_3ticks(levels: list[dict], ref_price: float, tick_size: float = 0.01, n_ticks: int = 3) -> float:
    """Sum dollar depth (price × size) for levels within n_ticks of ref_price."""
    total = 0.0
    threshold = n_ticks * tick_size
    for lvl in levels:
        try:
            px = float(lvl.get("price", 0) or 0)
            sz = float(lvl.get("size", 0) or 0)
            if abs(px - ref_price) <= threshold:
                total += px * sz
        except Exception:
            pass
    return total


def _get_ob_from_market_endpoint(market_id: str) -> dict[str, Any]:
    url = f"{GAMMA_MARKETS}/{market_id}"
    return retry_with_backoff(lambda: http_get_json(url), retries=2, backoff_ms=400)


def _get_ob_from_token_endpoint(token_id: str) -> dict[str, Any]:
    # Try CLOB API first (works with new long-form token IDs)
    try:
        url = f"{CLOB_BOOK}?token_id={token_id}"
        return retry_with_backoff(lambda: http_get_json(url), retries=2, backoff_ms=400)
    except Exception:
        pass
    # Fallback to Gamma OB endpoint (legacy short IDs)
    url = f"{GAMMA_OB}/{token_id}"
    return retry_with_backoff(lambda: http_get_json(url), retries=2, backoff_ms=400)


def get_orderbook_snapshot(market: Market) -> OBSnapshot:
    """
    Fetch live orderbook data and return a normalized OBSnapshot.
    Always returns an OBSnapshot (never raises) — check micro_ok.
    """
    bid_yes: float | None = None
    ask_yes: float | None = None
    bid_no: float | None = None
    ask_no: float | None = None
    depth_yes = 0.0
    depth_no = 0.0

    # ── Step 1: Get best bid/ask from market endpoint ──────────────────────────
    try:
        data = _get_ob_from_market_endpoint(market.market_id)
        if isinstance(data, list) and len(data) > 0:
            data = data[0]

        op_raw = data.get("outcomePrices") or "[]"
        if isinstance(op_raw, str):
            import json
            op = json.loads(op_raw)
        else:
            op = list(op_raw or [])

        yes_price = float(op[0]) if len(op) >= 1 and op[0] is not None else None

        best_bid = data.get("bestBid")
        best_ask = data.get("bestAsk")

        if best_bid is not None:
            bid_yes = float(best_bid)
        elif yes_price is not None:
            bid_yes = yes_price - 0.005

        if best_ask is not None:
            ask_yes = float(best_ask)
        elif yes_price is not None:
            ask_yes = yes_price + 0.005

        if bid_yes is not None:
            bid_no = 1.0 - ask_yes if ask_yes is not None else None
            ask_no = 1.0 - bid_yes

    except Exception as e:
        logger.debug("Market endpoint failed for %s: %s", market.market_id, e)

    # ── Step 2: Always fetch token OB for real 3-tick depth ────────────────────
    if market.yes_token_id:
        try:
            ob_yes = _get_ob_from_token_endpoint(market.yes_token_id)
            yes_bids = ob_yes.get("bids") or []
            yes_asks = ob_yes.get("asks") or []
            # Use token endpoint for bid/ask if market endpoint didn't provide them
            if bid_yes is None and yes_bids:
                bid_yes = float(yes_bids[0].get("price", 0))
            if ask_yes is None and yes_asks:
                ask_yes = float(yes_asks[0].get("price", 0))
            if bid_yes is not None and bid_no is None:
                bid_no = 1.0 - (ask_yes or bid_yes)
                ask_no = 1.0 - bid_yes
            # Sum bid+ask depth (Polymarket CLOBs often have asymmetric liquidity;
            # min would return 0 whenever one side posts via the opposing token)
            ref_bid = bid_yes or 0.5
            ref_ask = ask_yes or 0.5
            depth_yes = _depth_3ticks(yes_bids, ref_bid) + _depth_3ticks(yes_asks, ref_ask)
        except Exception as e:
            logger.debug("YES token OB failed for %s: %s", market.yes_token_id, e)

    if market.no_token_id and depth_yes >= MIN_DEPTH_TOP5_USD * 0.5:
        # Only fetch NO side when YES side shows enough depth to be worth checking.
        # Binary markets have symmetric depth; if YES is thin, NO will be too.
        try:
            ob_no = _get_ob_from_token_endpoint(market.no_token_id)
            no_bids = ob_no.get("bids") or []
            no_asks = ob_no.get("asks") or []
            ref_bid_no = bid_no or 0.5
            ref_ask_no = ask_no or 0.5
            depth_no = _depth_3ticks(no_bids, ref_bid_no) + _depth_3ticks(no_asks, ref_ask_no)
        except Exception as e:
            logger.debug("NO token OB failed for %s: %s", market.no_token_id, e)

    if bid_yes is None and ask_yes is None:
        return OBSnapshot(
            bid_yes=None, ask_yes=None, bid_no=None, ask_no=None,
            spread_yes=None, spread_no=None,
            depth_top5_usd_yes=0.0, depth_top5_usd_no=0.0,
            imbalance=0.0,
            micro_ok=False,
            micro_reason="empty_book",
            fetched_at=now_iso(),
        )

    def _clamp(v: float | None) -> float | None:
        return max(0.01, min(0.99, v)) if v is not None else None

    bid_yes = _clamp(bid_yes)
    ask_yes = _clamp(ask_yes)
    bid_no = _clamp(bid_no)
    ask_no = _clamp(ask_no)

    spread_yes = (ask_yes - bid_yes) if (ask_yes is not None and bid_yes is not None) else None
    spread_no = (ask_no - bid_no) if (ask_no is not None and bid_no is not None) else None

    imbalance = (depth_yes - depth_no) / (depth_yes + depth_no + 1e-9)

    spread_val = spread_yes if spread_yes is not None else 0.99
    depth_val = min(depth_yes, depth_no)

    if spread_val > MAX_SPREAD:
        return OBSnapshot(
            bid_yes=bid_yes, ask_yes=ask_yes, bid_no=bid_no, ask_no=ask_no,
            spread_yes=spread_yes, spread_no=spread_no,
            depth_top5_usd_yes=depth_yes, depth_top5_usd_no=depth_no,
            imbalance=imbalance,
            micro_ok=False,
            micro_reason="spread_too_wide",
            fetched_at=now_iso(),
        )

    if depth_val < MIN_DEPTH_TOP5_USD:
        return OBSnapshot(
            bid_yes=bid_yes, ask_yes=ask_yes, bid_no=bid_no, ask_no=ask_no,
            spread_yes=spread_yes, spread_no=spread_no,
            depth_top5_usd_yes=depth_yes, depth_top5_usd_no=depth_no,
            imbalance=imbalance,
            micro_ok=False,
            micro_reason="depth_too_low",
            fetched_at=now_iso(),
        )

    return OBSnapshot(
        bid_yes=bid_yes, ask_yes=ask_yes, bid_no=bid_no, ask_no=ask_no,
        spread_yes=spread_yes, spread_no=spread_no,
        depth_top5_usd_yes=depth_yes, depth_top5_usd_no=depth_no,
        imbalance=imbalance,
        micro_ok=True,
        micro_reason="",
        fetched_at=now_iso(),
    )
