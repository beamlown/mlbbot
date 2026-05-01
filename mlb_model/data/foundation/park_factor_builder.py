"""
data/foundation/park_factor_builder.py

Build a 3-year rolling run-scoring park factor table.

Park factor = (runs/game at this park) / (league avg runs/game across same window),
computed on a rolling N-year window ending in the row's season.

Output schema (parquet):
    season:    int
    park_id:   str
    run_factor: float   1.0 = neutral, >1 hitter-friendly, <1 pitcher-friendly
    n_games:    int     (sample size in window)
"""
from __future__ import annotations
import pandas as pd
from pathlib import Path

OUTPUT_PATH = Path("data/features/park_factors.parquet")


def compute_park_factors(game_logs: pd.DataFrame, rolling_years: int = 3) -> pd.DataFrame:
    """
    game_logs columns required: season, park_id, home_runs, away_runs
    Returns one row per (season, park_id).
    """
    if game_logs.empty:
        return pd.DataFrame(columns=["season", "park_id", "run_factor", "n_games"])

    gl = game_logs.copy()
    gl["total_runs"] = gl["home_runs"] + gl["away_runs"]

    seasons = sorted(gl["season"].unique())
    rows = []
    for season in seasons:
        window_start = season - rolling_years + 1
        window = gl[(gl["season"] >= window_start) & (gl["season"] <= season)]
        if window.empty:
            continue
        league_window_avg = window["total_runs"].mean()
        park_avg = window.groupby("park_id")["total_runs"].agg(["mean", "size"])
        for park_id, row in park_avg.iterrows():
            rf = row["mean"] / league_window_avg if league_window_avg > 0 else 1.0
            rows.append({
                "season": season,
                "park_id": park_id,
                "run_factor": float(rf),
                "n_games": int(row["size"]),
            })

    return pd.DataFrame(rows)


def build_from_retrosheet(retrosheet_dir: Path = Path("data/raw/retrosheet")) -> pd.DataFrame:
    """Load all retrosheet game-log parquets, compute factors, return df.

    Supports two schemas:
      - Canonical: HmRuns, VisRuns, ParkID, Date
      - This project's: h_name, v_name, h_score, v_score, date (derives park_id
        from home_team via sports.mlb.parks.TEAM_TO_PARK)
    """
    from sports.mlb.parks import lookup_park_id
    parquets = list(retrosheet_dir.glob("game_log_*.parquet"))
    if not parquets:
        raise FileNotFoundError(f"No retrosheet parquets in {retrosheet_dir}")
    frames = []
    for p in parquets:
        df = pd.read_parquet(p)
        if "HmRuns" in df.columns:
            df = df.rename(columns={"HmRuns": "home_runs", "VisRuns": "away_runs"})
        if "h_score" in df.columns and "home_runs" not in df.columns:
            df = df.rename(columns={"h_score": "home_runs", "v_score": "away_runs"})
        if "ParkID" in df.columns:
            df = df.rename(columns={"ParkID": "park_id"})
        if "park_id" not in df.columns and "h_name" in df.columns:
            df["park_id"] = df["h_name"].apply(lookup_park_id)
        if "Date" in df.columns and "season" not in df.columns:
            df["season"] = pd.to_datetime(df["Date"]).dt.year
        if "date" in df.columns and "season" not in df.columns:
            df["season"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce").dt.year
        cols_needed = ["season", "park_id", "home_runs", "away_runs"]
        missing = [c for c in cols_needed if c not in df.columns]
        if missing:
            raise ValueError(f"{p.name}: missing columns {missing} (have {list(df.columns)})")
        frames.append(df[cols_needed])
    all_logs = pd.concat(frames, ignore_index=True)
    all_logs = all_logs.dropna(subset=["season"])
    all_logs["season"] = all_logs["season"].astype(int)
    return compute_park_factors(all_logs, rolling_years=3)


def main() -> None:
    df = build_from_retrosheet()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
