"""
data/foundation/statcast_pitcher_aggregator.py

Aggregate Statcast pitch-by-pitch data into per-(pitcher_id, game_pk) FIP rows.
Output is the input format expected by
data.foundation.pitcher_quality_builder.compute_pitcher_quality_pointtime.

Statcast `events` field values used:
  out events (1 out each): generic_out, field_out, force_out, sac_fly, sac_bunt,
                           grounded_into_double_play (counts 2 outs in real life
                           but Statcast emits 1 event row), fielders_choice_out,
                           strikeout, strikeout_double_play (2 outs)
  K events:                strikeout, strikeout_double_play
  BB events:               walk, hit_by_pitch
  HR event:                home_run

For simplicity we count outs by counting events in _OUT_EVENTS (one event = one
out). Edge case: strikeout_double_play and grounded_into_double_play are 2 outs
each — handled explicitly with multipliers.
"""
from __future__ import annotations
import logging
import math
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("data/features/pitcher_quality.parquet")

_K_EVENTS = {"strikeout", "strikeout_double_play"}
_BB_EVENTS = {"walk", "hit_by_pitch"}

# Each entry maps event → outs recorded
_OUT_EVENTS = {
    "field_out": 1,
    "force_out": 1,
    "sac_fly": 1,
    "sac_fly_double_play": 2,
    "sac_bunt": 1,
    "sac_bunt_double_play": 2,
    "fielders_choice_out": 1,
    "fielders_choice": 1,
    "grounded_into_double_play": 2,
    "double_play": 2,
    "triple_play": 3,
    "strikeout": 1,
    "strikeout_double_play": 2,
    "other_out": 1,
    "caught_stealing_2b": 0,
    "caught_stealing_3b": 0,
    "caught_stealing_home": 0,
    "pickoff_1b": 0,
    "pickoff_2b": 0,
    "pickoff_3b": 0,
}


def _compute_fip(ip: float, hr: int, bb: int, k: int, constant: float = 3.2) -> float:
    """Classic FIP. Returns NaN if ip == 0."""
    if ip <= 0:
        return float("nan")
    return (13 * hr + 3 * bb - 2 * k) / ip + constant


def aggregate_per_pitcher_per_game(pitches: pd.DataFrame) -> pd.DataFrame:
    """
    pitches columns required: pitcher (int MLBAM ID), game_pk, game_date, events
    Returns: DataFrame with columns
        pitcher_id (int), game_pk, game_date (date), ip, k, bb, hr, fip, season
    Rows where events is NaN/null are ignored.
    """
    if pitches.empty:
        return pd.DataFrame(columns=["pitcher_id", "game_pk", "game_date",
                                     "ip", "k", "bb", "hr", "fip", "season"])

    df = pitches.copy()
    df = df.dropna(subset=["pitcher", "events"])
    if df.empty:
        return pd.DataFrame(columns=["pitcher_id", "game_pk", "game_date",
                                     "ip", "k", "bb", "hr", "fip", "season"])

    df["events"] = df["events"].astype(str)
    df["outs"] = df["events"].map(_OUT_EVENTS).fillna(0).astype(int)
    df["is_k"] = df["events"].isin(_K_EVENTS).astype(int)
    df["is_bb"] = df["events"].isin(_BB_EVENTS).astype(int)
    df["is_hr"] = (df["events"] == "home_run").astype(int)

    grouped = df.groupby(["pitcher", "game_pk", "game_date"], dropna=False).agg(
        outs=("outs", "sum"),
        k=("is_k", "sum"),
        bb=("is_bb", "sum"),
        hr=("is_hr", "sum"),
    ).reset_index()

    grouped = grouped.rename(columns={"pitcher": "pitcher_id"})
    grouped["pitcher_id"] = grouped["pitcher_id"].astype(int)
    grouped["ip"] = grouped["outs"] / 3.0
    grouped["fip"] = grouped.apply(
        lambda r: _compute_fip(r["ip"], r["hr"], r["bb"], r["k"]), axis=1
    )
    grouped["game_date"] = pd.to_datetime(grouped["game_date"]).dt.date
    grouped["season"] = pd.Series([d.year for d in grouped["game_date"]])

    return grouped[["pitcher_id", "game_pk", "game_date",
                    "ip", "k", "bb", "hr", "fip", "season"]]


def aggregate_from_statcast_dir(statcast_dir: Path = Path("data/raw/statcast"),
                                seasons: list[int] | None = None) -> pd.DataFrame:
    """Read all Statcast monthly parquets, aggregate, return combined DataFrame.

    Filters by season FIRST (cheap), then reads (expensive). Skips empty parquets
    (e.g. COVID-shortened 2020 March-June files have 0 columns).
    """
    import pyarrow.parquet as pq
    parquets = sorted(statcast_dir.glob("*.parquet"))
    if not parquets:
        raise FileNotFoundError(f"No Statcast parquets in {statcast_dir}")
    frames = []
    for p in parquets:
        # Cheap season filter on filename before opening the file
        if seasons is not None:
            yr_in_filename = None
            for tok in p.stem.replace("-", "_").split("_"):
                if tok.isdigit() and len(tok) == 4:
                    yr_in_filename = int(tok)
                    break
            if yr_in_filename is not None and yr_in_filename not in seasons:
                continue
        # Skip empty parquets (e.g. 2020_03..2020_06 have no games due to COVID)
        try:
            schema_cols = pq.read_schema(p).names
        except Exception as e:
            logger.warning("skipping unreadable parquet %s: %s", p.name, e)
            continue
        if "pitcher" not in schema_cols:
            logger.info("skipping empty/incomplete parquet %s (no 'pitcher' column)", p.name)
            continue
        df = pd.read_parquet(p, columns=["pitcher", "game_pk", "game_date", "events"])
        if df.empty:
            continue
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["pitcher_id", "game_pk", "game_date",
                                     "ip", "k", "bb", "hr", "fip", "season"])
    pitches = pd.concat(frames, ignore_index=True)
    return aggregate_per_pitcher_per_game(pitches)
