"""
integration/resolution_watcher.py — Poll Polymarket for resolved markets
and write outcome events to the shadow JSONL log.

Runs as a background process alongside recommendation_api.py.
When a market resolves, it calls ShadowLogger.log_outcome() so that
compute_shadow_pnl() can match recommendations to actual results.

Polymarket resolution logic:
  - Gamma API: GET /markets/{condition_id}
  - market.resolved = true when settled
  - market.outcomePrices = ["1", "0"] → YES won
  - market.outcomePrices = ["0", "1"] → NO won

Usage:
    python -m integration.resolution_watcher          # run forever
    python -m integration.resolution_watcher --once   # single pass, exit

Environment:
    GAMMA_API_URL         Polymarket Gamma API base (default: https://gamma-api.polymarket.com)
    SHADOW_LOG_PATH       Path to shadow JSONL (default: logs/shadow_recommendations.jsonl)
    RESOLUTION_POLL_SEC   Seconds between full polls (default: 120)
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

GAMMA_API_URL = os.getenv("GAMMA_API_URL", "https://gamma-api.polymarket.com")
SHADOW_LOG_PATH = Path(os.getenv("SHADOW_LOG_PATH", "logs/shadow_recommendations.jsonl"))
POLL_INTERVAL = int(os.getenv("RESOLUTION_POLL_SEC", "120"))


def _http_get(url: str, timeout: int = 10) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "mlb_model/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _load_pending_markets() -> dict[str, str]:
    """
    Scan shadow log for BUY_YES/BUY_NO recommendations that have no
    corresponding outcome event yet.
    Returns dict: market_id → market_slug (for logging).
    """
    if not SHADOW_LOG_PATH.exists():
        return {}

    seen_recs: dict[str, str] = {}   # market_id → market_slug
    resolved: set[str] = set()

    with open(SHADOW_LOG_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("event_type") == "outcome":
                resolved.add(obj["market_id"])
            elif obj.get("action") in ("BUY_YES", "BUY_NO"):
                mid = obj.get("market_id", "")
                if mid:
                    seen_recs[mid] = obj.get("market_slug", mid)

    return {mid: slug for mid, slug in seen_recs.items() if mid not in resolved}


def _check_resolution(market_id: str) -> tuple[bool, bool]:
    """
    Query Gamma API for a single market.
    Returns (is_resolved: bool, yes_resolved: bool).
    yes_resolved is only meaningful when is_resolved is True.
    """
    try:
        url = f"{GAMMA_API_URL}/markets/{market_id}"
        data = _http_get(url)

        if not data.get("resolved"):
            return False, False

        # outcomePrices is a JSON-encoded list like '["1", "0"]' or ["1", "0"]
        outcome_prices_raw = data.get("outcomePrices") or data.get("outcome_prices")
        if outcome_prices_raw:
            if isinstance(outcome_prices_raw, str):
                try:
                    outcome_prices_raw = json.loads(outcome_prices_raw)
                except json.JSONDecodeError:
                    pass
            if isinstance(outcome_prices_raw, list) and len(outcome_prices_raw) >= 2:
                yes_price = float(outcome_prices_raw[0])
                yes_resolved = yes_price >= 0.99
                return True, yes_resolved

        # Fallback: check resolution field directly
        resolution = str(data.get("resolution") or "").upper()
        if resolution in ("YES", "1", "TRUE"):
            return True, True
        elif resolution in ("NO", "0", "FALSE"):
            return True, False

        # Market is resolved but outcome is ambiguous — treat as resolved-no-trade
        logger.warning("Market %s resolved but outcome unclear: %s", market_id[:16], data)
        return True, False

    except Exception as e:
        logger.debug("Resolution check failed for %s: %s", market_id[:16], e)
        return False, False


def run_once(shadow_log) -> int:
    """
    Single resolution pass. Returns number of new outcomes logged.
    shadow_log: ShadowLogger instance.
    """
    pending = _load_pending_markets()
    if not pending:
        logger.debug("Resolution watcher: no pending markets to check")
        return 0

    logger.info("Resolution watcher: checking %d pending markets", len(pending))
    logged = 0

    for market_id, slug in pending.items():
        is_resolved, yes_resolved = _check_resolution(market_id)
        if is_resolved:
            shadow_log.log_outcome(market_id, yes_resolved)
            logger.info(
                "Outcome logged: market=%s slug=%s yes_resolved=%s",
                market_id[:16], slug[:30], yes_resolved,
            )
            logged += 1
        time.sleep(0.3)  # gentle rate limiting

    return logged


def main():
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Poll Polymarket for resolved markets")
    parser.add_argument("--once", action="store_true",
                        help="Run a single pass then exit")
    parser.add_argument("--poll-sec", type=int, default=POLL_INTERVAL,
                        help=f"Seconds between polls (default: {POLL_INTERVAL})")
    args = parser.parse_args()

    from integration.shadow_mode_logger import ShadowLogger
    shadow_log = ShadowLogger()

    logger.info("Resolution watcher starting (poll every %ds, log=%s)",
                args.poll_sec, SHADOW_LOG_PATH)

    if args.once:
        n = run_once(shadow_log)
        logger.info("Single pass complete: %d outcomes logged", n)
        return

    while True:
        try:
            n = run_once(shadow_log)
            if n:
                logger.info("Logged %d new outcome(s)", n)
        except Exception as e:
            logger.error("Resolution watcher error: %s", e, exc_info=True)
        time.sleep(args.poll_sec)


if __name__ == "__main__":
    main()
