"""scripts/refresh_bullpen_quality_daily.py — Daily rolling bullpen avg refresh."""
from __future__ import annotations
import logging
import os
from datetime import date
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

BULLPEN_PATH = Path("data/features/bullpen_quality.parquet")


def main() -> int:
    """
    Refresh bullpen quality for today by rebuilding from the current +1 season
    slice of Statcast (bullpen is rolling 30d, so only recent months needed).
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    from data.foundation.bullpen_aggregator import build_from_statcast

    today = date.today()
    df = build_from_statcast(seasons=list(range(today.year - 1, today.year + 1)))
    if df.empty:
        print("bullpen aggregator produced no rows")
        return 0

    BULLPEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = BULLPEN_PATH.with_suffix(".parquet.tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, BULLPEN_PATH)
    print(f"Wrote {len(df)} rows to {BULLPEN_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
