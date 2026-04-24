import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from core.db import fetch_open_trades

LOGGER = logging.getLogger("resolution_watcher")
POLL_INTERVAL_SECONDS = 60
GAMMA_API_URL = "https://gamma-api.polymarket.com/markets?id={market_id}"
ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_FILE = ROOT_DIR / "runtime" / "resolved_markets.json"


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def _load_existing_state() -> dict:
    if not OUTPUT_FILE.exists():
        return {}
    try:
        with OUTPUT_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        LOGGER.warning("Failed to read %s: %s", OUTPUT_FILE, exc)
        return {}


def _atomic_write_state(state: dict) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        dir=str(OUTPUT_FILE.parent),
        prefix="resolved_markets.",
        suffix=".json.tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(state, tmp, indent=2, sort_keys=True)
        os.replace(temp_path, OUTPUT_FILE)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fetch_market_resolution(market_id: str):
    url = GAMMA_API_URL.format(market_id=market_id)
    try:
        with urlopen(url, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        LOGGER.warning("Failed to fetch market %s: %s", market_id, exc)
        return None
    except Exception as exc:
        LOGGER.warning("Unexpected response for market %s: %s", market_id, exc)
        return None

    if not isinstance(payload, list) or not payload:
        LOGGER.warning("No market data returned for market %s", market_id)
        return None

    market = payload[0] if isinstance(payload[0], dict) else {}
    resolved = bool(market.get("resolved", False))
    if not resolved:
        return None

    outcome_prices = market.get("outcomePrices", ["0", "0"])
    yes_price = _safe_float(outcome_prices[0] if len(outcome_prices) > 0 else 0.0)
    no_price = _safe_float(outcome_prices[1] if len(outcome_prices) > 1 else 0.0)

    return {
        "resolved": True,
        "yes_resolution_price": yes_price,
        "no_resolution_price": no_price,
        "slug": market.get("slug"),
        "resolved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def run() -> None:
    _setup_logging()
    state = _load_existing_state()

    # Ensure file exists even before first resolution.
    try:
        _atomic_write_state(state)
    except Exception as exc:
        LOGGER.error("Failed to initialize state file %s: %s", OUTPUT_FILE, exc)

    while True:
        try:
            state = _load_existing_state()

            try:
                open_trades = fetch_open_trades()
            except Exception as exc:
                LOGGER.error("fetch_open_trades() failed: %s", exc)
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            open_market_ids = {
                str(trade.market_id)
                for trade in open_trades
                if getattr(trade, "market_id", None) is not None
            }

            unresolved_market_ids = [
                market_id
                for market_id in open_market_ids
                if not bool(state.get(market_id, {}).get("resolved", False))
            ]

            for market_id in unresolved_market_ids:
                result = _fetch_market_resolution(market_id)
                if not result:
                    continue

                state[market_id] = result
                _atomic_write_state(state)
                LOGGER.info(
                    "Market %s resolved (YES=%.4f, NO=%.4f, slug=%s)",
                    market_id,
                    result["yes_resolution_price"],
                    result["no_resolution_price"],
                    result.get("slug"),
                )
        except Exception as exc:
            LOGGER.error("Unhandled watcher error: %s", exc)

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
