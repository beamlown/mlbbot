"""
data/pregame_prior_builder.py — Elo-based pregame win probability prior

Builds a team Elo table from historical Retrosheet game logs and returns
calibrated pregame P(home wins) for each game.

Elo design:
  - Initial rating: 1500 for all teams
  - Season-to-season regression: carry 50% toward 1500
  - Home field advantage: +65 Elo points effective
  - K-factor: 20 regular season, 15 postseason
  - Expected score formula: 1 / (1 + 10^((elo_opp - elo_home - HFA) / 400))

The Elo table is saved to data/features/elo_table.parquet:
  season, date, home_team, away_team, elo_home_pre, elo_away_pre, p_home_elo

Usage:
    python -m data.pregame_prior_builder --seasons 2018 2019 2020 2021 2022 2023 2024 2025
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

# Elo hyper-params
ELO_INIT = 1500.0
ELO_HFA = 65.0        # home field advantage in Elo points
K_REGULAR = 20.0
K_POST = 15.0
SEASON_REGRESSION = 0.50   # pull toward mean between seasons


def _elo_expected(elo_home: float, elo_away: float) -> float:
    """P(home wins) given Elo ratings (with HFA already embedded in elo_home)."""
    return 1.0 / (1.0 + 10.0 ** ((elo_away - elo_home) / 400.0))


def _elo_update(elo: float, expected: float, actual: float, k: float) -> float:
    return elo + k * (actual - expected)


def _normalize_team(abbrev: str) -> str:
    """Normalize historical team abbreviations to a stable canonical form."""
    abbrev = str(abbrev).strip().upper()
    # Retrosheet uses classic abbreviations; map known changes
    _MAP = {
        "FLO": "MIA",   # Marlins
        "MON": "WSN",   # Expos → Nationals
        "ANA": "LAA",   # Angels
        "CAL": "LAA",
        "TBD": "TBR",   # Devil Rays
        "CLE": "CLE",
    }
    return _MAP.get(abbrev, abbrev)


def _retrosheet_columns(df: pd.DataFrame) -> dict[str, str] | None:
    """
    Retrosheet game log column names vary by pybaseball version.
    Try to find the relevant columns and return a name map.
    """
    cols = set(df.columns.str.lower())

    # pybaseball >=2.2 retrosheet_game_log uses positional columns with names like
    # 'date', 'v_name', 'h_name', 'v_score', 'h_score', 'game_type'
    # Older versions may use integers or different names.
    candidates = {
        "date": ["date", "game_date", "Date"],
        "away": ["v_name", "away_team", "visitor_team", "VisitingTeam"],
        "home": ["h_name", "home_team", "HomeTeam"],
        "away_score": ["v_score", "away_score", "VisitorRunsScored"],
        "home_score": ["h_score", "home_score", "HomeRunsScore"],
        "game_type": ["game_type", "GameType", "day_night"],
    }

    result = {}
    for key, options in candidates.items():
        for opt in options:
            if opt.lower() in cols or opt in df.columns:
                # find actual column name (case-sensitive)
                actual = next((c for c in df.columns if c.lower() == opt.lower()), opt)
                result[key] = actual
                break
        if key not in result and key in ("date", "away", "home", "away_score", "home_score"):
            logger.warning("Could not find column for '%s' in retrosheet data. Columns: %s",
                           key, list(df.columns[:20]))
            return None
    return result


def build_elo_table(game_log_df: pd.DataFrame, seasons: list[int]) -> pd.DataFrame:
    """
    Process game log rows chronologically, updating Elo after each game.
    Returns a DataFrame with pre-game Elo and P(home wins) for each game.
    """
    col_map = _retrosheet_columns(game_log_df)
    if col_map is None:
        raise ValueError("Cannot parse Retrosheet game log — unknown column format")

    # Normalize relevant columns
    df = game_log_df.copy()
    df["_date"] = pd.to_datetime(df[col_map["date"]], errors="coerce")
    df["_home"] = df[col_map["home"]].apply(_normalize_team)
    df["_away"] = df[col_map["away"]].apply(_normalize_team)
    df["_h_score"] = pd.to_numeric(df[col_map["home_score"]], errors="coerce")
    df["_a_score"] = pd.to_numeric(df[col_map["away_score"]], errors="coerce")
    df["_season"] = df["_date"].dt.year

    # Drop rows with missing essentials
    df = df.dropna(subset=["_date", "_home", "_away", "_h_score", "_a_score"])
    df = df.sort_values("_date").reset_index(drop=True)

    # Determine if postseason
    if "game_type" in col_map and col_map["game_type"] in df.columns:
        df["_is_post"] = df[col_map["game_type"]].isin(["F", "D", "L", "W"])
    else:
        df["_is_post"] = False

    elo: dict[str, float] = {}
    records: list[dict] = []
    current_season = None

    for _, row in df.iterrows():
        season = int(row["_season"])
        home = row["_home"]
        away = row["_away"]
        h_score = row["_h_score"]
        a_score = row["_a_score"]
        is_post = bool(row["_is_post"])

        # Season-start Elo regression
        if season != current_season:
            if current_season is not None:
                for team in list(elo.keys()):
                    elo[team] = elo[team] * (1 - SEASON_REGRESSION) + ELO_INIT * SEASON_REGRESSION
            current_season = season

        # Initialize new teams
        elo.setdefault(home, ELO_INIT)
        elo.setdefault(away, ELO_INIT)

        elo_home_pre = elo[home]
        elo_away_pre = elo[away]

        # Expected with HFA
        elo_home_eff = elo_home_pre + ELO_HFA
        p_home = _elo_expected(elo_home_eff, elo_away_pre)

        # Actual outcome
        if h_score > a_score:
            actual = 1.0
        elif h_score < a_score:
            actual = 0.0
        else:
            actual = 0.5  # tie (extremely rare in MLB; extra innings always resolve)

        # Update
        k = K_POST if is_post else K_REGULAR
        elo[home] = _elo_update(elo_home_pre, p_home, actual, k)
        elo[away] = _elo_update(elo_away_pre, p_home, 1.0 - actual, k)

        records.append({
            "season": season,
            "date": row["_date"].date().isoformat(),
            "home_team": home,
            "away_team": away,
            "elo_home_pre": round(elo_home_pre, 2),
            "elo_away_pre": round(elo_away_pre, 2),
            "elo_home_eff": round(elo_home_eff, 2),
            "p_home_elo": round(p_home, 6),
            "home_score": int(h_score),
            "away_score": int(a_score),
            "home_won": int(actual == 1.0),
        })

    result = pd.DataFrame(records)
    return result


def save_elo_table(df: pd.DataFrame) -> Path:
    FEATURE_DIR.mkdir(parents=True, exist_ok=True)
    path = FEATURE_DIR / "elo_table.parquet"
    df.to_parquet(path, index=False)
    logger.info("Saved Elo table: %s (%d rows)", path, len(df))
    return path


def load_elo_table() -> pd.DataFrame:
    path = FEATURE_DIR / "elo_table.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Elo table not found at {path}. Run pregame_prior_builder first.")
    return pd.read_parquet(path)


def get_pregame_prob(home_team: str, away_team: str, date: str, elo_table: pd.DataFrame) -> float:
    """
    Look up the pregame P(home wins) for a specific game from the Elo table.
    Falls back to 0.54 (slight home field advantage prior) if not found.
    """
    mask = (
        (elo_table["home_team"] == home_team) &
        (elo_table["away_team"] == away_team) &
        (elo_table["date"] == date)
    )
    rows = elo_table[mask]
    if rows.empty:
        logger.debug("No Elo entry for %s vs %s on %s — using default 0.54", home_team, away_team, date)
        return 0.54  # slight home field advantage prior
    return float(rows.iloc[0]["p_home_elo"])


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Build Elo pregame prior table")
    parser.add_argument("--seasons", nargs="+", type=int,
                        default=list(range(2010, 2026)),
                        help="Seasons to include (use more history for better Elo convergence)")
    args = parser.parse_args()

    from data.retrosheet_ingest import load_retrosheet_seasons
    logger.info("Loading Retrosheet game logs for %d seasons ...", len(args.seasons))
    game_log = load_retrosheet_seasons(args.seasons)

    if game_log.empty:
        logger.error("No game log data. Run retrosheet_ingest first.")
        return

    logger.info("Building Elo table from %d games ...", len(game_log))
    elo_df = build_elo_table(game_log, args.seasons)
    save_elo_table(elo_df)

    # Quick sanity check
    subset = elo_df[elo_df["season"].isin([2023, 2024, 2025])]
    mean_p = subset["p_home_elo"].mean()
    logger.info("Sanity check — mean P(home wins) in 2023-2025: %.4f (expected ~0.53-0.55)", mean_p)
    actual_hw = subset["home_won"].mean()
    logger.info("Actual home win rate in 2023-2025: %.4f", actual_hw)


if __name__ == "__main__":
    main()
