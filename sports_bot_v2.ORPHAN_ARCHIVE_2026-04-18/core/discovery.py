"""
core/discovery.py — Polymarket Gamma API market discovery
Parameterized for any sport via adapter config. Sport-agnostic engine.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import date, timedelta
from typing import Any

from core.types import Market
from core.utils import atomic_write_json, http_get_json, now_iso, retry_with_backoff

logger = logging.getLogger("core.discovery")

GAMMA_EVENTS = "https://gamma-api.polymarket.com/events"
GAMMA_MARKETS = "https://gamma-api.polymarket.com/markets"

DISCOVERY_CACHE_TTL_SEC = int(os.getenv("DISCOVERY_CACHE_TTL_SEC", "60"))
DISCOVERY_CACHE_PATH = os.getenv("DISCOVERY_CACHE_PATH", "runtime/last_discovery.json")

_SPREAD_DIR_RE = re.compile(r"-spread-(home|away)-(\d+(?:pt\d+)?)", re.IGNORECASE)
_TOTAL_RE = re.compile(r"-total-(\d+(?:pt\d+)?)", re.IGNORECASE)
_TOTAL_Q_RE = re.compile(r'\b(?:over|under|o/u|ou)\b.*?(\d+(?:\.\d+)?)', re.IGNORECASE)
_ALT_TOTAL_RE = re.compile(r'-(?:over|under|ou)-(\d+(?:pt\d+)?)', re.IGNORECASE)
_SPREAD_Q_RE = re.compile(r'[+-]?(\d+(?:\.\d+)?)\s*(?:run|rl\b)', re.IGNORECASE)

_SLUG_DATE_RE = re.compile(r'(\d{4}-\d{2}-\d{2})')
_GAME_DATE_WINDOW_PAST = int(os.getenv("GAME_DATE_WINDOW_PAST", "1"))
_GAME_DATE_WINDOW_FUTURE = int(os.getenv("GAME_DATE_WINDOW_FUTURE", "2"))

_CACHE: dict[str, tuple[float, list[Market]]] = {}


def _is_game_event(event_slug: str, game_event_re: re.Pattern | None) -> bool:
    """Return True if event_slug matches the per-game pattern and falls within the date window."""
    if game_event_re is None:
        return True
    m = game_event_re.match(event_slug)
    if not m:
        return False
    # If the pattern captures a date group, enforce the window
    dm = _SLUG_DATE_RE.search(event_slug)
    if dm:
        try:
            game_date = date.fromisoformat(dm.group(1))
            today = date.today()
            if game_date < today - timedelta(days=_GAME_DATE_WINDOW_PAST):
                return False
            if game_date > today + timedelta(days=_GAME_DATE_WINDOW_FUTURE):
                return False
        except ValueError:
            pass
    return True


def _parse_pts(raw: str) -> float:
    """'7pt5' → 7.5, '158pt5' → 158.5, '10' → 10.0"""
    return float(raw.replace("pt", "."))


def classify_market(slug: str, question: str) -> tuple[str, float | None, float | None]:
    """Returns (market_type, spread_line, total_line). Universal for any sport."""
    slug_lc = slug.lower()
    q_lc = question.lower()

    # Slug-based (existing patterns for old-style markets)
    m = _SPREAD_DIR_RE.search(slug_lc)
    if m:
        return "spread", _parse_pts(m.group(2)), None
    m = _TOTAL_RE.search(slug_lc)
    if m:
        return "total", None, _parse_pts(m.group(1))

    # Question-based O/U detection (Polymarket sports style)
    # e.g. "Will Rangers and Orioles combine for over 9.5 runs?"
    m = _TOTAL_Q_RE.search(q_lc)
    if m:
        try:
            return "total", None, float(m.group(1))
        except ValueError:
            pass

    # Slug-based O/U alternate patterns: -over-, -under-, -ou-
    m = _ALT_TOTAL_RE.search(slug_lc)
    if m:
        return "total", None, _parse_pts(m.group(1))

    # Question-based spread detection
    # e.g. "Will Phillies cover the -1.5 run line?"
    if any(kw in q_lc for kw in ("run line", "spread", "cover the", "rl ")):
        m = _SPREAD_Q_RE.search(q_lc)
        if m:
            try:
                return "spread", float(m.group(1)), None
            except ValueError:
                pass

    # Moneyline if "win" or " vs " in question
    if " vs" in q_lc or " win" in q_lc or "moneyline" in q_lc:
        return "moneyline", None, None

    return "other", None, None


def _is_sport_market(j: dict[str, Any], keywords: list[str]) -> bool:
    question = (j.get("question") or j.get("title") or "").lower()
    tags = [str(t).lower() for t in (j.get("tags") or [])]
    if any(kw in question for kw in keywords):
        return True
    tag_str = " ".join(tags)
    if any(kw in tag_str for kw in keywords):
        return True
    return False


def _parse_market(
    j: dict[str, Any],
    event_slug: str,
    sport: str,
    tournament: str,
) -> Market | None:
    try:
        market_id = str(j.get("id") or j.get("conditionId") or "")
        if not market_id:
            return None

        slug = str(j.get("slug") or "")
        question = str(j.get("question") or j.get("title") or "")

        clob_ids_raw = j.get("clobTokenIds") or j.get("clob_token_ids") or "[]"
        if isinstance(clob_ids_raw, str):
            try:
                clob_ids = json.loads(clob_ids_raw)
            except Exception:
                clob_ids = []
        else:
            clob_ids = list(clob_ids_raw)

        yes_token_id = str(clob_ids[0]) if len(clob_ids) > 0 else ""
        no_token_id = str(clob_ids[1]) if len(clob_ids) > 1 else ""

        op_raw = j.get("outcomePrices") or j.get("outcome_prices") or "[]"
        if isinstance(op_raw, str):
            try:
                op = json.loads(op_raw)
            except Exception:
                op = []
        else:
            op = list(op_raw)

        yes_price = float(op[0]) if len(op) >= 1 and op[0] is not None else None
        no_price = float(op[1]) if len(op) >= 2 and op[1] is not None else None

        active = bool(j.get("active", True))
        closed = bool(j.get("closed", False))
        resolved = bool(j.get("resolved", False))
        mtype, spread_ln, total_ln = classify_market(slug, question)

        volume24h_raw = j.get("volume24hr") or j.get("volume24h")
        volume24h = float(volume24h_raw) if volume24h_raw is not None else None

        return Market(
            market_id=market_id,
            event_slug=event_slug or str(j.get("eventSlug") or ""),
            slug=slug,
            question=question,
            yes_token_id=yes_token_id,
            no_token_id=no_token_id,
            start_iso=str(j.get("gameStartTime") or j.get("startDateIso") or j.get("startDate") or "") or None,
            end_iso=str(j.get("endDateIso") or j.get("endDate") or "") or None,
            sport=sport,
            tournament=tournament,
            yes_price=yes_price,
            no_price=no_price,
            volume24h=volume24h,
            active=active,
            closed=closed,
            resolved=resolved,
            market_type=mtype,
            spread_line=spread_ln,
            total_line=total_ln,
        )
    except Exception as e:
        logger.debug("_parse_market error: %s | raw=%s", e, str(j)[:120])
        return None


def _fetch_by_tag(
    tag_slug: str,
    sport: str,
    tournament: str,
    game_event_re: re.Pattern | None = None,
) -> list[Market]:
    url = f"{GAMMA_EVENTS}?tag_slug={tag_slug}&closed=false&limit=500"
    logger.debug("Discovery: GET %s", url)
    data = retry_with_backoff(lambda: http_get_json(url), retries=3, backoff_ms=600)

    markets: list[Market] = []
    events = data if isinstance(data, list) else data.get("events", [])
    skipped = 0
    for event in events:
        event_slug = str(event.get("slug") or "")
        if not _is_game_event(event_slug, game_event_re):
            skipped += 1
            continue
        for mkt_raw in (event.get("markets") or []):
            m = _parse_market(mkt_raw, event_slug, sport, tournament)
            if m and not m.closed and not m.resolved:
                markets.append(m)
    if skipped:
        logger.debug("Discovery (tag=%s): skipped %d non-game events", tag_slug, skipped)
    logger.info("Discovery (tag=%s): found %d markets", tag_slug, len(markets))
    return markets


def _fetch_fallback_filter(keywords: list[str], sport: str, tournament: str) -> list[Market]:
    url = f"{GAMMA_MARKETS}?active=true&closed=false&limit=500"
    logger.debug("Discovery fallback: GET %s", url)
    data = retry_with_backoff(lambda: http_get_json(url), retries=3, backoff_ms=600)
    rows = data if isinstance(data, list) else data.get("markets", [])

    markets: list[Market] = []
    for row in rows:
        if _is_sport_market(row, keywords):
            m = _parse_market(row, "", sport, tournament)
            if m and not m.closed and not m.resolved:
                markets.append(m)
    logger.info("Discovery (fallback, %s): found %d markets", sport, len(markets))
    return markets


def discover_markets(
    tag_slug: str,
    keywords: list[str],
    sport: str,
    tournament: str,
    force_refresh: bool = False,
    game_event_re: re.Pattern | None = None,
) -> list[Market]:
    """
    Returns live markets for the specified sport.
    Uses in-memory TTL cache. Tries tag endpoint first, falls back to keyword filter.
    """
    cache_key = f"{sport}_{tournament}"
    if not force_refresh:
        cached = _CACHE.get(cache_key)
        if cached:
            ts, mkts = cached
            if time.time() - ts < DISCOVERY_CACHE_TTL_SEC:
                return mkts

    markets: list[Market] = []
    errors: list[str] = []

    try:
        markets = _fetch_by_tag(tag_slug, sport, tournament, game_event_re=game_event_re)
    except Exception as e:
        errors.append(f"tag_fetch: {e}")
        logger.warning("Tag discovery failed: %s — trying fallback", e)

    if not markets:
        try:
            markets = _fetch_fallback_filter(keywords, sport, tournament)
        except Exception as e:
            errors.append(f"fallback_fetch: {e}")
            logger.error("Fallback discovery also failed: %s", e)

    if not markets and errors:
        cached = _CACHE.get(cache_key)
        if cached:
            _, stale_markets = cached
            logger.warning("All discovery failed — returning stale cache (%d markets)", len(stale_markets))
            return stale_markets

    _CACHE[cache_key] = (time.time(), markets)

    try:
        atomic_write_json(DISCOVERY_CACHE_PATH, {
            "fetched_at": now_iso(),
            "sport": sport,
            "tournament": tournament,
            "count": len(markets),
            "errors": errors,
            "markets": [
                {
                    "market_id": m.market_id,
                    "slug": m.slug,
                    "question": m.question,
                    "yes_token_id": m.yes_token_id,
                    "no_token_id": m.no_token_id,
                    "yes_price": m.yes_price,
                    "no_price": m.no_price,
                    "end_iso": m.end_iso,
                    "active": m.active,
                    "closed": m.closed,
                    "resolved": m.resolved,
                }
                for m in markets
            ],
        })
    except Exception as e:
        logger.debug("Failed to persist discovery cache: %s", e)

    return markets
