"""
data/state_snapshot_builder.py — Build game-state snapshot rows from Statcast pitch data

For each game in the Statcast data, this module:
  1. Groups pitches by game
  2. Identifies plate appearance (PA) boundaries — first pitch of each at-bat
  3. Records game state at each PA boundary:
     score, inning, half, outs, base runners, pitcher, pitch count, TTO proxy
  4. Computes total pitches thrown per pitcher up to each PA (for fatigue features)
  5. Labels each row with the final game outcome (home team won)
  6. Joins with pregame Elo prior

One snapshot row per PA boundary per game.
The home team's perspective is always the "tracked team":
  - y = 1 if home team wins
  - score_diff = home_score - away_score (from home team's perspective)

To get away team perspective: flip sign of score_diff, is_home=0, y = 1-y

Output schema (per handoff spec):
  game_id, date, season, home_team, away_team,
  inning, half (0=top, 1=bottom), outs, home_score, away_score, score_diff,
  base_state (0-7), game_progress (0-1), outs_elapsed,
  home_pitcher_id, away_pitcher_id,
  home_pitch_count, away_pitch_count,
  home_tto, away_tto,                   -- times through order proxy
  home_is_bullpen, away_is_bullpen,
  pregame_win_prob (P(home wins)),
  home_elo, away_elo,
  home_won_final (y)

Usage:
    python -m data.state_snapshot_builder --seasons 2022 2023 2024
"""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

FEATURE_DIR = Path(os.getenv("FEATURE_DIR", "data/features"))

# Outs in a standard 9-inning game
STANDARD_GAME_OUTS = 54

# Heuristic: if pitcher has thrown >= STARTER_PITCH_THRESHOLD pitches, classify as starter
# If pitch count is 0 and they're the first pitcher, also starter
STARTER_PITCH_THRESHOLD = 20   # they threw at least 20 pitches in starter role


def _base_state(on_1b, on_2b, on_3b) -> int:
    """Encode base runner situation as 0-7 integer."""
    b1 = 0 if (pd.isna(on_1b) or on_1b == 0) else 1
    b2 = 0 if (pd.isna(on_2b) or on_2b == 0) else 1
    b3 = 0 if (pd.isna(on_3b) or on_3b == 0) else 1
    return b1 * 1 + b2 * 2 + b3 * 4


def _base_state_value(bs: int) -> float:
    """Approximate run expectancy weight for base state (relative to empty)."""
    # Rough run expectancy weights based on base state
    _WEIGHTS = {0: 0.0, 1: 0.9, 2: 1.1, 3: 1.3, 4: 1.6, 5: 1.8, 6: 1.9, 7: 2.3}
    return _WEIGHTS.get(bs, 0.0)


def _outs_elapsed(inning: int, inning_half: int, outs: int) -> int:
    """Total outs elapsed in game at start of this PA."""
    completed_half_innings = (inning - 1) * 2 + inning_half
    return completed_half_innings * 3 + outs


def build_snapshots_for_season(
    statcast_df: pd.DataFrame,
    elo_table: pd.DataFrame,
    season: int,
) -> pd.DataFrame:
    """
    Build snapshot rows for all games in a season's Statcast data.
    Returns a DataFrame of snapshot rows.
    """
    if statcast_df.empty:
        return pd.DataFrame()

    # Ensure required columns exist
    required_cols = [
        "game_pk", "game_date", "inning", "inning_topbot",
        "outs_when_up", "at_bat_number", "pitch_number",
        "home_score", "away_score",
        "home_team", "away_team",
        "pitcher", "batter",
    ]
    missing = [c for c in required_cols if c not in statcast_df.columns]
    if missing:
        logger.error("Missing Statcast columns: %s", missing)
        return pd.DataFrame()

    # Base runner columns (may not always be present in older data)
    for col in ["on_1b", "on_2b", "on_3b"]:
        if col not in statcast_df.columns:
            statcast_df[col] = np.nan

    # Convert types
    df = statcast_df.copy()
    df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
    df["inning"] = pd.to_numeric(df["inning"], errors="coerce").fillna(1).astype(int)
    df["outs_when_up"] = pd.to_numeric(df["outs_when_up"], errors="coerce").fillna(0).astype(int)
    df["at_bat_number"] = pd.to_numeric(df["at_bat_number"], errors="coerce").fillna(0).astype(int)
    df["pitch_number"] = pd.to_numeric(df["pitch_number"], errors="coerce").fillna(1).astype(int)
    df["home_score"] = pd.to_numeric(df["home_score"], errors="coerce").fillna(0).astype(int)
    df["away_score"] = pd.to_numeric(df["away_score"], errors="coerce").fillna(0).astype(int)
    df["inning_half"] = (df["inning_topbot"].str.lower().str.strip() == "bot").astype(int)

    # Sort for processing
    df = df.sort_values(["game_pk", "at_bat_number", "pitch_number"]).reset_index(drop=True)

    all_snapshots: list[dict] = []

    for game_pk, game_df in df.groupby("game_pk"):
        game_df = game_df.sort_values(["at_bat_number", "pitch_number"])

        # Get game metadata
        game_date_str = game_df["game_date"].iloc[0].date().isoformat() if not game_df["game_date"].isna().all() else ""
        home_team = str(game_df["home_team"].iloc[0]).upper()
        away_team = str(game_df["away_team"].iloc[0]).upper()

        # Final game score: use max scores observed (post_home_score / post_away_score if available)
        if "post_home_score" in game_df.columns and "post_away_score" in game_df.columns:
            final_home = int(game_df["post_home_score"].max())
            final_away = int(game_df["post_away_score"].max())
        else:
            final_home = int(game_df["home_score"].max())
            final_away = int(game_df["away_score"].max())

        home_won = 1 if final_home > final_away else 0

        # Pregame Elo prior
        pregame_prob = 0.54  # default
        home_elo = 1500.0
        away_elo = 1500.0
        if not elo_table.empty:
            mask = (
                (elo_table["home_team"] == home_team) &
                (elo_table["away_team"] == away_team) &
                (elo_table["date"] == game_date_str)
            )
            elo_rows = elo_table[mask]
            if not elo_rows.empty:
                pregame_prob = float(elo_rows.iloc[0]["p_home_elo"])
                home_elo = float(elo_rows.iloc[0]["elo_home_pre"])
                away_elo = float(elo_rows.iloc[0]["elo_away_pre"])

        # Compute cumulative pitch counts per pitcher per game
        # (needed for pitcher fatigue features)
        pitch_counts: dict[int, int] = {}      # pitcher_id → pitches thrown so far
        pitcher_entry_ab: dict[int, int] = {}  # pitcher_id → first AB number they pitched

        # Track starter: first pitcher to appear for each side
        home_starter_id: int | None = None
        away_starter_id: int | None = None

        # Identify PAs (first pitch of each at_bat_number)
        pa_df = game_df.drop_duplicates(subset=["at_bat_number"], keep="first")

        for _, pitch_row in game_df.iterrows():
            pitcher_id = int(pitch_row["pitcher"]) if not pd.isna(pitch_row["pitcher"]) else -1
            inning_h = int(pitch_row["inning_half"])

            # Track who pitched first for each team
            if inning_h == 0 and home_starter_id is None:
                # Top of inning → away team batting → home team pitching... wait
                # inning_topbot "Top" means AWAY team is batting, HOME pitcher is on mound
                home_starter_id = pitcher_id
            elif inning_h == 1 and away_starter_id is None:
                away_starter_id = pitcher_id

            # Track entry at-bat for each pitcher
            ab_num = int(pitch_row["at_bat_number"])
            if pitcher_id not in pitcher_entry_ab:
                pitcher_entry_ab[pitcher_id] = ab_num

        # Now iterate PA boundaries and build snapshots
        for _, pa_row in pa_df.iterrows():
            ab_num = int(pa_row["at_bat_number"])
            inning = int(pa_row["inning"])
            inning_h = int(pa_row["inning_half"])  # 0=top, 1=bottom
            outs = int(pa_row["outs_when_up"])
            h_score = int(pa_row["home_score"])
            a_score = int(pa_row["away_score"])

            # Base runners at start of this PA
            bs = _base_state(pa_row["on_1b"], pa_row["on_2b"], pa_row["on_3b"])

            # Current pitcher (pitching team's pitcher)
            pitcher_id = int(pa_row["pitcher"]) if not pd.isna(pa_row["pitcher"]) else -1

            # Pitches thrown by this pitcher up to (not including) this PA
            # Count pitches in game_df with this pitcher and ab_num < current
            pitcher_game = game_df[game_df["pitcher"] == pitcher_id]
            pitches_so_far = int((pitcher_game["at_bat_number"] < ab_num).sum())

            # Who is pitching? Top of inning = home team pitching
            if inning_h == 0:  # top: away bats, home pitches
                home_pitcher_id = pitcher_id
                home_pitch_count = pitches_so_far
                away_pitch_count = 0  # away pitcher not on mound this PA
                home_is_bullpen = 0 if pitcher_id == home_starter_id else 1
                away_is_bullpen = 0
                # TTO: approximate times through order for current pitcher
                # (pitcher_entry_ab gives first AB they faced)
                entry_ab = pitcher_entry_ab.get(pitcher_id, ab_num)
                abs_faced = ab_num - entry_ab
                home_tto = min(3.0, abs_faced / 9.0 + 1.0)
                away_tto = 0.0
                away_pitcher_id = away_starter_id or -1
            else:  # bottom: home bats, away pitches
                away_pitcher_id = pitcher_id
                away_pitch_count = pitches_so_far
                home_pitch_count = 0
                away_is_bullpen = 0 if pitcher_id == away_starter_id else 1
                home_is_bullpen = 0
                entry_ab = pitcher_entry_ab.get(pitcher_id, ab_num)
                abs_faced = ab_num - entry_ab
                away_tto = min(3.0, abs_faced / 9.0 + 1.0)
                home_tto = 0.0
                home_pitcher_id = home_starter_id or -1

            outs_el = _outs_elapsed(inning, inning_h, outs)
            total_game_outs = STANDARD_GAME_OUTS if inning <= 9 else STANDARD_GAME_OUTS + (inning - 9) * 6
            game_progress = min(1.0, outs_el / STANDARD_GAME_OUTS)

            all_snapshots.append({
                "game_id": str(game_pk),
                "date": game_date_str,
                "season": season,
                "home_team": home_team,
                "away_team": away_team,
                "inning": inning,
                "half": inning_h,            # 0=top, 1=bottom
                "outs": outs,
                "home_score": h_score,
                "away_score": a_score,
                "score_diff": h_score - a_score,
                "base_state": bs,
                "base_state_value": _base_state_value(bs),
                "outs_elapsed": outs_el,
                "game_progress": round(game_progress, 4),
                "home_pitcher_id": home_pitcher_id,
                "away_pitcher_id": away_pitcher_id,
                "home_pitch_count": home_pitch_count,
                "away_pitch_count": away_pitch_count,
                "home_tto": round(home_tto, 2),
                "away_tto": round(away_tto, 2),
                "home_is_bullpen": home_is_bullpen,
                "away_is_bullpen": away_is_bullpen,
                "pregame_win_prob": round(pregame_prob, 6),
                "home_elo": round(home_elo, 2),
                "away_elo": round(away_elo, 2),
                "home_won_final": home_won,
            })

    if not all_snapshots:
        return pd.DataFrame()

    result = pd.DataFrame(all_snapshots)
    logger.info("Season %d: built %d snapshot rows from %d games",
                season, len(result), result["game_id"].nunique())
    return result


def save_snapshots(df: pd.DataFrame, season: int) -> Path:
    FEATURE_DIR.mkdir(parents=True, exist_ok=True)
    path = FEATURE_DIR / f"snapshots_{season}.parquet"
    df.to_parquet(path, index=False)
    logger.info("Saved snapshots: %s", path)
    return path


def load_snapshots(seasons: list[int]) -> pd.DataFrame:
    parts = []
    for season in seasons:
        path = FEATURE_DIR / f"snapshots_{season}.parquet"
        if path.exists():
            parts.append(pd.read_parquet(path))
        else:
            logger.warning("No snapshot file for season %d. Run state_snapshot_builder first.", season)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Build game-state snapshots from Statcast")
    parser.add_argument("--seasons", nargs="+", type=int, default=[2023, 2024])
    args = parser.parse_args()

    from data.retrosheet_ingest import load_statcast_season
    from data.pregame_prior_builder import load_elo_table

    try:
        elo_table = load_elo_table()
        logger.info("Loaded Elo table: %d entries", len(elo_table))
    except FileNotFoundError:
        logger.warning("Elo table not found — using default 0.54 prior for all games.")
        elo_table = pd.DataFrame()

    for season in args.seasons:
        logger.info("Processing season %d ...", season)
        statcast_df = load_statcast_season(season)
        if statcast_df.empty:
            logger.error("No statcast data for %d. Run retrosheet_ingest first.", season)
            continue
        snaps = build_snapshots_for_season(statcast_df, elo_table, season)
        if not snaps.empty:
            save_snapshots(snaps, season)

    logger.info("Snapshot build complete.")


if __name__ == "__main__":
    main()
