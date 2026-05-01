"""
data/foundation/reliever_quality_builder.py

Point-in-time reliever quality (FIP-) per (pitcher_id, as_of_date).

Hybrid: 0.6 * current_STD + 0.4 * prior_season, regressed toward league mean
by IP (REGRESSION_IP=25 for relievers, smaller than starter's 60).

CRITICAL: only outings with game_date < as_of_date contribute.
"""
from __future__ import annotations
import logging
from datetime import date
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("data/features/reliever_quality.parquet")
LEAGUE_FIP_DEFAULT = 4.00
REGRESSION_IP = 25.0
PRIOR_WEIGHT = 0.4


def _hybrid_fip_minus(prior_fip: float | None, std_fip: float | None,
                      std_ip: float, league_fip: float = LEAGUE_FIP_DEFAULT) -> float:
    has_prior = prior_fip is not None and not pd.isna(prior_fip)
    has_std = std_fip is not None and not pd.isna(std_fip)
    if not has_prior and not has_std:
        return 100.0
    if not has_prior:
        raw = std_fip
    elif not has_std:
        raw = prior_fip
    else:
        raw = (1.0 - PRIOR_WEIGHT) * std_fip + PRIOR_WEIGHT * prior_fip
    weight = std_ip / (std_ip + REGRESSION_IP) if std_ip > 0 else 0.0
    regressed = weight * raw + (1.0 - weight) * league_fip
    return (regressed / league_fip) * 100.0


def compute_reliever_quality_pointtime(
    history: pd.DataFrame,
    snapshot_dates: list[date] | None = None,
) -> pd.DataFrame:
    """
    history columns: pitcher_id, game_date, ip, fip, season
    Returns: pitcher_id, as_of_date, reliever_quality, n_outings_std
    """
    cols = ["pitcher_id", "as_of_date", "reliever_quality", "n_outings_std"]
    if history.empty:
        return pd.DataFrame(columns=cols)

    h = history.copy()
    h["game_date"] = pd.to_datetime(h["game_date"]).dt.date

    if snapshot_dates is None:
        snapshot_dates = sorted(set(h["game_date"].tolist()))

    pitchers = h["pitcher_id"].unique()
    out_rows = []
    for pid in pitchers:
        ph = h[h["pitcher_id"] == pid]
        for as_of in snapshot_dates:
            past = ph[ph["game_date"] < as_of]
            if past.empty:
                continue
            cur_season = as_of.year
            std = past[past["season"] == cur_season]
            prior = past[past["season"] == cur_season - 1]
            std_ip = float(std["ip"].sum()) if not std.empty else 0.0
            std_fip = float((std["fip"] * std["ip"]).sum() / std_ip) if std_ip > 0 else None
            prior_ip = float(prior["ip"].sum()) if not prior.empty else 0.0
            prior_fip = float((prior["fip"] * prior["ip"]).sum() / prior_ip) if prior_ip > 0 else None
            q = _hybrid_fip_minus(prior_fip, std_fip, std_ip)
            out_rows.append({
                "pitcher_id": pid,
                "as_of_date": as_of,
                "reliever_quality": q,
                "n_outings_std": int(len(std)),
            })
    return pd.DataFrame(out_rows, columns=cols)


def build_from_statcast(seasons: list[int] | None = None) -> pd.DataFrame:
    from data.foundation.statcast_reliever_aggregator import aggregate_from_statcast_dir
    history = aggregate_from_statcast_dir(seasons=seasons)
    if history.empty:
        return pd.DataFrame(columns=["pitcher_id", "as_of_date", "reliever_quality", "n_outings_std"])
    history["pitcher_id"] = history["pitcher_id"].astype(str)
    return compute_reliever_quality_pointtime(
        history[["pitcher_id", "game_date", "ip", "fip", "season"]]
    )


def main() -> None:
    seasons = list(range(2018, 2026))
    df = build_from_statcast(seasons)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
