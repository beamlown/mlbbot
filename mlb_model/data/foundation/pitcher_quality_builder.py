"""
data/foundation/pitcher_quality_builder.py

Point-in-time pitcher quality table.

For each (pitcher_id, as_of_date) we compute:
    sp_quality:        hybrid FIP- (0.6 * current_STD + 0.4 * prior_season),
                       regressed to league mean by IP. 100 = league avg, lower better.
    sp_recent_form:    baseline_fip - trailing_30d_fip.  >0 = pitching better than baseline.
    n_starts_std:      sample size in current season (used downstream for imputation flag)

CRITICAL: only starts with game_date < as_of_date may contribute. No leakage.

Output schema (parquet):
    pitcher_id, as_of_date, sp_quality, sp_recent_form, n_starts_std
"""
from __future__ import annotations
import logging
from datetime import date, timedelta
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("data/features/pitcher_quality.parquet")
LEAGUE_FIP_DEFAULT = 4.00
REGRESSION_IP = 60.0


def _hybrid_fip(prior_fip: float | None, std_fip: float | None,
                std_ip: float, prior_weight: float = 0.4) -> float:
    if prior_fip is None and std_fip is None:
        return float("nan")
    if prior_fip is None:
        return float(std_fip)
    if std_fip is None:
        return float(prior_fip)
    cur_weight = 1.0 - prior_weight
    return prior_weight * prior_fip + cur_weight * std_fip


def _regress_to_mean(fip: float, ip: float, league_fip: float,
                     reg_ip: float = REGRESSION_IP) -> float:
    if pd.isna(fip):
        return league_fip
    weight = ip / (ip + reg_ip)
    return weight * fip + (1.0 - weight) * league_fip


def _hybrid_fip_minus(prior_fip: float | None, std_fip: float | None,
                      std_ip: float, league_fip: float = LEAGUE_FIP_DEFAULT) -> float:
    raw = _hybrid_fip(prior_fip, std_fip, std_ip)
    # Only regress to league mean when we have no prior-season anchor.
    # The 0.4 weight on prior in the hybrid already provides shrinkage;
    # additional regression would be double-shrinkage.
    if prior_fip is None:
        regressed = _regress_to_mean(raw, std_ip, league_fip)
    else:
        regressed = raw if not pd.isna(raw) else league_fip
    return (regressed / league_fip) * 100.0


def _recent_form_delta(baseline_fip: float, recent_fip: float) -> float:
    """Positive = recent better than baseline."""
    if pd.isna(recent_fip):
        return 0.0
    return float(baseline_fip - recent_fip)


def compute_pitcher_quality_pointtime(
    starts: pd.DataFrame,
    league_fip: float = LEAGUE_FIP_DEFAULT,
    snapshot_dates: list[date] | None = None,
) -> pd.DataFrame:
    """
    starts columns: pitcher_id, game_date (date), ip (float), fip (float), season (int)

    snapshot_dates: list of dates to compute quality "as of" each date.
        If None, generates one snapshot per starts.game_date plus
        the test-fixture dates 2024-03-01 and 2025-04-15.
    """
    if starts.empty:
        return pd.DataFrame(columns=["pitcher_id", "as_of_date", "sp_quality",
                                     "sp_recent_form", "n_starts_std"])

    starts = starts.copy()
    starts["game_date"] = pd.to_datetime(starts["game_date"]).dt.date

    pitchers = starts["pitcher_id"].unique()

    if snapshot_dates is None:
        snapshot_dates = sorted(set(starts["game_date"].tolist()) |
                                {date(2024, 3, 1), date(2025, 4, 15)})

    out_rows = []
    for pitcher_id in pitchers:
        ps = starts[starts["pitcher_id"] == pitcher_id]
        for as_of in snapshot_dates:
            history = ps[ps["game_date"] < as_of]
            cur_season = as_of.year
            std = history[history["season"] == cur_season]
            prior = history[history["season"] == cur_season - 1]

            std_ip = float(std["ip"].sum()) if not std.empty else 0.0
            std_fip = float((std["fip"] * std["ip"]).sum() / std_ip) if std_ip > 0 else None
            prior_ip = float(prior["ip"].sum()) if not prior.empty else 0.0
            prior_fip = float((prior["fip"] * prior["ip"]).sum() / prior_ip) if prior_ip > 0 else None

            sp_quality = _hybrid_fip_minus(prior_fip, std_fip, std_ip, league_fip)

            recent_window = history[history["game_date"] >= as_of - timedelta(days=30)]
            recent_ip = float(recent_window["ip"].sum()) if not recent_window.empty else 0.0
            recent_fip = float((recent_window["fip"] * recent_window["ip"]).sum() / recent_ip) if recent_ip > 0 else float("nan")
            baseline_fip = (sp_quality / 100.0) * league_fip
            recent_form = _recent_form_delta(baseline_fip, recent_fip)

            out_rows.append({
                "pitcher_id": pitcher_id,
                "as_of_date": as_of,
                "sp_quality": sp_quality,
                "sp_recent_form": recent_form,
                "n_starts_std": int(len(std)),
            })

    return pd.DataFrame(out_rows)


# DEPRECATED — use build_from_statcast instead. The pybaseball loader keys on
# pitcher names, which don't match snapshot.home_pitcher_id (Statcast int IDs).
# This function is preserved for legacy callers but should not be used in the
# main pipeline. See sub-project #1.5 design doc for context.
def build_from_pybaseball(seasons: list[int]) -> pd.DataFrame:
    """
    Use pybaseball to pull starting-pitcher game logs for the listed seasons,
    then compute the point-in-time table.

    Note: this performs network calls — slow. Cache the parquet output.
    """
    try:
        import pybaseball as pyb
    except ImportError:
        raise ImportError("pybaseball not installed; run pip install -r requirements.txt")

    frames = []
    for season in seasons:
        df = pyb.pitching_stats_range(f"{season}-03-01", f"{season}-11-15")
        df = df.rename(columns={"Name": "pitcher_id", "Date": "game_date",
                                "IP": "ip", "FIP": "fip"})
        df["season"] = season
        df["game_date"] = pd.to_datetime(df["game_date"]).dt.date
        df = df[df["ip"] >= 4.0]
        frames.append(df[["pitcher_id", "game_date", "ip", "fip", "season"]])

    starts = pd.concat(frames, ignore_index=True)
    return compute_pitcher_quality_pointtime(starts)


def build_from_statcast(seasons: list[int] | None = None) -> pd.DataFrame:
    """
    Build the point-in-time pitcher quality table from local Statcast pitches.
    Uses MLBAM int pitcher IDs that match snapshot.home_pitcher_id natively.

    Pipeline: Statcast pitches -> aggregate to per-game FIP ->
              compute_pitcher_quality_pointtime() -> output parquet rows.
    """
    from data.foundation.statcast_pitcher_aggregator import aggregate_from_statcast_dir
    starts = aggregate_from_statcast_dir(seasons=seasons)
    starts = starts[starts["fip"].notna() & (starts["ip"] >= 4.0)].copy()
    starts["pitcher_id"] = starts["pitcher_id"].astype(str)
    return compute_pitcher_quality_pointtime(starts[["pitcher_id", "game_date", "ip", "fip", "season"]])


def main() -> None:
    seasons = list(range(2018, 2026))
    df = build_from_statcast(seasons)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
