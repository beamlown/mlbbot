"""
data/foundation/statcast_reliever_aggregator.py

Aggregate Statcast pitches into per-(pitcher, game) relief-FIP rows.
Thin wrapper over statcast_pitcher_aggregator with IP<4.0 filter (relief outings).

Output schema mirrors pitcher aggregator:
    pitcher_id (int), game_pk, game_date (date),
    ip, k, bb, hr, fip, season
"""
from __future__ import annotations
import logging
from pathlib import Path
import pandas as pd

from data.foundation.statcast_pitcher_aggregator import aggregate_per_pitcher_per_game

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("data/features/reliever_quality.parquet")
RELIEF_IP_MAX = 4.0


def aggregate_reliever_per_game(pitches: pd.DataFrame) -> pd.DataFrame:
    """Aggregate via pitcher aggregator, then filter to relief outings only (IP<4)."""
    full = aggregate_per_pitcher_per_game(pitches)
    if full.empty:
        return full
    return full[full["ip"] < RELIEF_IP_MAX].reset_index(drop=True)


def aggregate_from_statcast_dir(statcast_dir: Path = Path("data/raw/statcast"),
                                seasons: list[int] | None = None) -> pd.DataFrame:
    """Read Statcast parquets, filter to relief outings, return combined DataFrame.

    Filters by season FIRST (cheap), then reads. Skips empty parquets.
    """
    import pyarrow.parquet as pq
    parquets = sorted(statcast_dir.glob("*.parquet"))
    if not parquets:
        raise FileNotFoundError(f"No Statcast parquets in {statcast_dir}")
    frames = []
    for p in parquets:
        if seasons is not None:
            yr = None
            for tok in p.stem.replace("-", "_").split("_"):
                if tok.isdigit() and len(tok) == 4:
                    yr = int(tok)
                    break
            if yr is not None and yr not in seasons:
                continue
        try:
            schema_cols = pq.read_schema(p).names
        except Exception as e:
            logger.warning("skipping unreadable parquet %s: %s", p.name, e)
            continue
        if "pitcher" not in schema_cols:
            continue
        df = pd.read_parquet(p, columns=["pitcher", "game_pk", "game_date", "events"])
        if df.empty:
            continue
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["pitcher_id", "game_pk", "game_date",
                                     "ip", "k", "bb", "hr", "fip", "season"])
    return aggregate_reliever_per_game(pd.concat(frames, ignore_index=True))
