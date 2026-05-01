"""
data/foundation/bullpen_aggregator.py

Rolling team-level bullpen quality: weighted-mean relief-FIP across the
8 most-active relievers per team in a trailing N-day window.

Output: (team, as_of_date, bullpen_avg_quality, n_relievers)
"""
from __future__ import annotations
import logging
from datetime import date, timedelta
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("data/features/bullpen_quality.parquet")
LEAGUE_FIP = 4.0
TOP_N_RELIEVERS = 8
DEFAULT_WINDOW_DAYS = 30


def compute_bullpen_quality(
    history: pd.DataFrame,
    as_of: date,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> pd.DataFrame:
    """
    history columns: pitcher_id, team, game_date, ip, fip
    Returns one row per team for as_of date.
    """
    cols = ["team", "as_of_date", "bullpen_avg_quality", "n_relievers"]
    if history.empty:
        return pd.DataFrame(columns=cols)

    h = history.copy()
    h["game_date"] = pd.to_datetime(h["game_date"]).dt.date
    window_start = as_of - timedelta(days=window_days)
    window = h[(h["game_date"] >= window_start) & (h["game_date"] < as_of)]
    if window.empty:
        return pd.DataFrame(columns=cols)

    rows = []
    for team, team_df in window.groupby("team"):
        counts = team_df.groupby("pitcher_id").size().sort_values(ascending=False)
        top_ids = counts.head(TOP_N_RELIEVERS).index.tolist()
        top_outings = team_df[team_df["pitcher_id"].isin(top_ids)]
        total_ip = float(top_outings["ip"].sum())
        if total_ip <= 0:
            continue
        weighted_fip = float((top_outings["fip"] * top_outings["ip"]).sum() / total_ip)
        bullpen_quality = (weighted_fip / LEAGUE_FIP) * 100.0
        rows.append({
            "team": team,
            "as_of_date": as_of,
            "bullpen_avg_quality": bullpen_quality,
            "n_relievers": len(top_ids),
        })
    return pd.DataFrame(rows, columns=cols)


def build_from_statcast(seasons: list[int] | None = None) -> pd.DataFrame:
    """Build bullpen quality rolling-30d snapshots at each unique game_date."""
    from data.foundation.statcast_reliever_aggregator import aggregate_from_statcast_dir
    import pyarrow.parquet as pq
    from pathlib import Path as _P

    history = aggregate_from_statcast_dir(seasons=seasons)
    if history.empty:
        return pd.DataFrame(columns=["team", "as_of_date", "bullpen_avg_quality", "n_relievers"])

    statcast_dir = _P("data/raw/statcast")
    parquets = sorted(statcast_dir.glob("*.parquet"))
    team_frames = []
    for p in parquets:
        try:
            cols = pq.read_schema(p).names
        except Exception:
            continue
        if "pitcher" not in cols:
            continue
        df = pd.read_parquet(p, columns=["pitcher", "game_pk", "home_team",
                                         "away_team", "inning_topbot"])
        if df.empty:
            continue
        df["team"] = df.apply(
            lambda r: r["home_team"] if r["inning_topbot"] == "Top" else r["away_team"],
            axis=1,
        )
        team_frames.append(df[["pitcher", "game_pk", "team"]].drop_duplicates(
            subset=["pitcher", "game_pk"]))
    if not team_frames:
        return pd.DataFrame(columns=["team", "as_of_date", "bullpen_avg_quality", "n_relievers"])

    teams = pd.concat(team_frames, ignore_index=True)
    teams = teams.rename(columns={"pitcher": "pitcher_id"})
    teams["pitcher_id"] = teams["pitcher_id"].astype(str)
    history["pitcher_id"] = history["pitcher_id"].astype(str)
    merged = history.merge(teams, on=["pitcher_id", "game_pk"], how="left")
    merged = merged.dropna(subset=["team"])

    snapshots = sorted(merged["game_date"].unique())
    out_frames = []
    for d in snapshots:
        bq = compute_bullpen_quality(merged, as_of=d)
        if not bq.empty:
            out_frames.append(bq)
    if not out_frames:
        return pd.DataFrame(columns=["team", "as_of_date", "bullpen_avg_quality", "n_relievers"])
    return pd.concat(out_frames, ignore_index=True)


def main() -> None:
    seasons = list(range(2018, 2026))
    df = build_from_statcast(seasons)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
