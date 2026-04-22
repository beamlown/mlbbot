"""
core/polymarket_client.py — Typed facade over the Polymarket CLOB.

This module is the single route for all Polymarket HTTP traffic. It wraps
py_clob_client with:
  - typed return shapes (dict[token_id, float] instead of dict[token_id, str])
  - 429 Retry-After-aware retries via core.utils.retry_with_backoff
  - disk-persisted tick-size cache surviving process restarts

Unauthenticated endpoints only (midpoints/prices/spreads/last_trade_price/tick_size).
Authenticated endpoints (place_order, cancel_order) come with Stair C.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BookParams

from core.utils import retry_with_backoff

logger = logging.getLogger("core.polymarket_client")

CLOB_HOST = os.getenv("CLOB_HOST", "https://clob.polymarket.com")
POLYGON_CHAIN_ID = int(os.getenv("POLYGON_CHAIN_ID", "137"))
TICK_SIZE_CACHE_PATH = Path(os.getenv("TICK_SIZE_CACHE_PATH", "runtime/tick_sizes.json"))
RETRIES = int(os.getenv("POLYMARKET_CLIENT_RETRIES", "3"))
BACKOFF_MS = int(os.getenv("POLYMARKET_CLIENT_BACKOFF_MS", "500"))

_client: ClobClient | None = None
_tick_cache: dict[str, float] = {}
_tick_cache_loaded: bool = False


def _get_client() -> ClobClient:
    global _client
    if _client is None:
        _client = ClobClient(host=CLOB_HOST, chain_id=POLYGON_CHAIN_ID)
    return _client


def _load_tick_cache() -> None:
    global _tick_cache, _tick_cache_loaded
    if _tick_cache_loaded:
        return
    _tick_cache_loaded = True
    if not TICK_SIZE_CACHE_PATH.exists():
        return
    try:
        raw = json.loads(TICK_SIZE_CACHE_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            _tick_cache = {str(k): float(v) for k, v in raw.items()}
        logger.info("tick_size cache loaded n=%d path=%s", len(_tick_cache), TICK_SIZE_CACHE_PATH)
    except Exception as exc:
        logger.warning("tick_size cache load failed path=%s err=%s", TICK_SIZE_CACHE_PATH, exc)
        _tick_cache = {}


def _save_tick_cache() -> None:
    try:
        TICK_SIZE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        TICK_SIZE_CACHE_PATH.write_text(json.dumps(_tick_cache, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("tick_size cache save failed path=%s err=%s", TICK_SIZE_CACHE_PATH, exc)


def _coerce_batch_float_dict(
    resp: Any,
    label: str,
    extractor: Callable[[Any], Any] = lambda v: v,
) -> dict[str, float]:
    """Normalize a batch-endpoint response into {token_id: float}.

    `resp` is expected to be a dict[str, Any] from py_clob_client. `extractor`
    picks the numeric value out of each entry — defaults to identity for flat
    shapes like get_midpoints/get_spreads; batch_prices uses a side-picker.

    Tokens with non-numeric or missing values are logged at WARN and omitted
    rather than aborting the whole batch.
    """
    out: dict[str, float] = {}
    if not isinstance(resp, dict):
        logger.warning("%s: non-dict response type=%s", label, type(resp).__name__)
        return out
    for tid, raw in resp.items():
        try:
            out[str(tid)] = float(extractor(raw))
        except (TypeError, ValueError, KeyError, AttributeError):
            logger.warning("%s: unparseable token=%s val=%r", label, tid, raw)
    return out


# --- batch endpoints (stubs — filled in by subsequent tasks) ------------------
def batch_midpoints(token_ids: list[str]) -> dict[str, float]:
    """Fetch midpoint (bid+ask)/2 for each token. Returns {token_id: mid_float}.

    Tokens not known to the CLOB are silently omitted from the result.
    """
    if not token_ids:
        return {}
    client = _get_client()
    params = [BookParams(token_id=tid) for tid in token_ids]
    resp = retry_with_backoff(
        lambda: client.get_midpoints(params=params),
        retries=RETRIES, backoff_ms=BACKOFF_MS,
    )
    return _coerce_batch_float_dict(resp, "batch_midpoints")

def batch_prices(token_ids: list[str], side: str = "SELL") -> dict[str, float]:
    """Fetch best price for each token on the requested side.

    side: "BUY" (best bid) or "SELL" (best ask).
    Returns {token_id: price_float}. Unknown tokens omitted.
    """
    if side not in ("BUY", "SELL"):
        raise ValueError(f"side must be BUY or SELL, got {side!r}")
    if not token_ids:
        return {}
    client = _get_client()
    params = [BookParams(token_id=tid, side=side) for tid in token_ids]
    resp = retry_with_backoff(
        lambda: client.get_prices(params=params),
        retries=RETRIES, backoff_ms=BACKOFF_MS,
    )

    def _pick_side(entry):
        if isinstance(entry, dict):
            return entry.get(side)
        return entry

    return _coerce_batch_float_dict(resp, "batch_prices", extractor=_pick_side)

def batch_spreads(token_ids: list[str]) -> dict[str, float]:
    """Fetch bid-ask spread for each token. Returns {token_id: spread_float}."""
    if not token_ids:
        return {}
    client = _get_client()
    params = [BookParams(token_id=tid) for tid in token_ids]
    resp = retry_with_backoff(
        lambda: client.get_spreads(params=params),
        retries=RETRIES, backoff_ms=BACKOFF_MS,
    )
    return _coerce_batch_float_dict(resp, "batch_spreads")

def last_trade_price(token_id: str) -> tuple[float, int] | None:
    """Return (price, unix_ts) of the last executed trade for a token.
    Returns None if the market has no trades yet."""
    client = _get_client()
    resp = retry_with_backoff(
        lambda: client.get_last_trade_price(token_id=token_id),
        retries=RETRIES, backoff_ms=BACKOFF_MS,
    )
    if not isinstance(resp, dict) or not resp:
        return None
    raw_price = resp.get("price")
    raw_ts = resp.get("timestamp") or resp.get("ts") or 0
    try:
        return (float(raw_price), int(float(raw_ts)))
    except (TypeError, ValueError):
        logger.warning("last_trade_price: unparseable token=%s resp=%r", token_id, resp)
        return None

def tick_size(token_id: str) -> float:
    """Return tick size (minimum price increment) for a token.

    Result is cached in-memory AND persisted to TICK_SIZE_CACHE_PATH so it
    survives process restarts. First call per token hits the CLOB; subsequent
    calls serve from cache.
    """
    _load_tick_cache()
    if token_id in _tick_cache:
        return _tick_cache[token_id]
    client = _get_client()
    resp = retry_with_backoff(
        lambda: client.get_tick_size(token_id=token_id),
        retries=RETRIES, backoff_ms=BACKOFF_MS,
    )
    try:
        tick = float(resp)
    except (TypeError, ValueError):
        logger.warning("tick_size: unparseable token=%s resp=%r; defaulting to 0.01", token_id, resp)
        tick = 0.01
    _tick_cache[token_id] = tick
    _save_tick_cache()
    return tick


def refresh_tick_sizes(token_ids: list[str]) -> int:
    """Prefetch tick sizes for multiple tokens. Returns count of tokens newly fetched.

    Tokens already in cache are skipped. Fetch failures log a warning and do
    not abort the batch.
    """
    _load_tick_cache()
    fetched = 0
    for tid in token_ids:
        if tid in _tick_cache:
            continue
        try:
            tick_size(tid)  # writes to cache + disk
            fetched += 1
        except Exception as exc:
            logger.warning("refresh_tick_sizes: fetch failed token=%s err=%s", tid, exc)
    return fetched
