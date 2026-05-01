"""
data/foundation/statcast_batter_aggregator.py

Aggregate Statcast pitch data into per-(batter_id, game_date) xwOBA rows.
Uses estimated_woba_using_speedangle (xwOBA) — Statcast's predicted wOBA from
launch angle + exit velocity. Walks/HBP have no xwoba (no batted ball), so
they're counted in PA but not in the xwoba_mean.

Output schema:
    batter_id (int), game_date (date), xwoba_mean (float),
    pa (int), xwoba_pa (int), season (int)
"""
from __future__ import annotations
import logging
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

LEAGUE_AVG_XWOBA = 0.320


def _scale_to_100(xwoba: float, league_avg: float = LEAGUE_AVG_XWOBA) -> float:
    """Scale raw xwoba to 100-centered (>100 = above avg, lower = below)."""
    if league_avg <= 0:
        return 100.0
    return (xwoba / league_avg) * 100.0


def aggregate_per_batter_per_date(pitches: pd.DataFrame) -> pd.DataFrame:
    """
    pitches columns: batter (int MLBAM), game_date, estimated_woba_using_speedangle, events
    Returns one row per (batter, date) with mean xwoba over batted-ball PAs + raw PA count.
    Rows where events is null (pre-PA-end pitches) are ignored.
    """
    cols = ["batter_id", "game_date", "xwoba_mean", "pa", "xwoba_pa", "season"]
    if pitches.empty:
        return pd.DataFrame(columns=cols)

    df = pitches.copy()
    df = df.dropna(subset=["batter", "events"])
    if df.empty:
        return pd.DataFrame(columns=cols)

    df["batter"] = df["batter"].astype(int)
    df["xwoba"] = pd.to_numeric(df.get("estimated_woba_using_speedangle"), errors="coerce")

    agg = df.groupby(["batter", "game_date"], dropna=False).agg(
        pa=("events", "count"),
        xwoba_mean=("xwoba", "mean"),
        xwoba_pa=("xwoba", lambda s: int(s.notna().sum())),
    ).reset_index()

    agg = agg.rename(columns={"batter": "batter_id"})
    agg["game_date"] = pd.to_datetime(agg["game_date"]).dt.date
    agg["season"] = pd.Series([d.year for d in agg["game_date"]])
    return agg[cols]


def aggregate_from_statcast_dir(statcast_dir: Path = Path("data/raw/statcast"),
                                seasons: list[int] | None = None) -> pd.DataFrame:
    """Read all Statcast monthly parquets, aggregate, return combined DataFrame.

    Filters by season FIRST (cheap), then reads. Skips empty parquets (e.g. COVID 2020).
    """
    import pyarrow.parquet as pq
    parquets = sorted(statcast_dir.glob("*.parquet"))
    if not parquets:
        raise FileNotFoundError(f"No Statcast parquets in {statcast_dir}")
    cols_needed = ["batter", "game_date", "events", "estimated_woba_using_speedangle"]
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
        if "batter" not in schema_cols:
            logger.info("skipping empty/incomplete parquet %s", p.name)
            continue
        df = pd.read_parquet(p, columns=cols_needed)
        if df.empty:
            continue
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["batter_id", "game_date", "xwoba_mean",
                                     "pa", "xwoba_pa", "season"])
    return aggregate_per_batter_per_date(pd.concat(frames, ignore_index=True))
