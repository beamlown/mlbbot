"""Cron entry: snapshot today's Pinnacle MLB moneylines."""
import logging
from data.foundation.sharp_odds_fetcher import snapshot, SharpOddsError

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    try:
        n = snapshot()
        print(f"Snapshotted {n} events")
    except SharpOddsError as e:
        logging.error("Snapshot failed: %s", e)
        raise SystemExit(1)
