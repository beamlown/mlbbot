"""
data/retrosheet_ingest.py — Historical MLB data ingest via pybaseball (Statcast + Retrosheet)

Two data sources:
  1. Statcast pitch-by-pitch (2015+) via pybaseball.statcast()
     Used to build game-state snapshots at each plate-appearance boundary.
  2. Retrosheet game logs (direct download from retrosheet.org)
     Used to build the Elo prior table (all games with final scores).
     pybaseball.retrosheet_game_log() is NOT used — that API does not exist in
     current pybaseball releases. We download directly from:
       https://www.retrosheet.org/gamelogs/gl{year}.zip

Cache strategy: each downloaded batch is saved as parquet in RAW_DATA_DIR.
Re-runs skip re-downloading if the cache file exists.

Usage:
    python -m data.retrosheet_ingest --seasons 2018 2019 2020 2021 2022 2023 2024 2025
"""
from __future__ import annotations

import argparse
import logging
import os
import time
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

RAW_DATA_DIR = Path(os.getenv("RAW_DATA_DIR", "data/raw"))
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)


# ── Statcast pitch-by-pitch ────────────────────────────────────────────────────

def _statcast_cache_path(year: int, month: int) -> Path:
    return RAW_DATA_DIR / "statcast" / f"{year}_{month:02d}.parquet"


def fetch_statcast_month(year: int, month: int, force: bool = False) -> pd.DataFrame:
    """
    Download one month of Statcast data and cache to parquet.
    Returns the DataFrame (may be empty if no games that month).
    """
    import calendar
    cache = _statcast_cache_path(year, month)
    if cache.exists() and not force:
        logger.info("statcast cache hit: %s", cache)
        return pd.read_parquet(cache)

    # Date range for the month
    _, last_day = calendar.monthrange(year, month)
    start = f"{year}-{month:02d}-01"
    end = f"{year}-{month:02d}-{last_day:02d}"

    logger.info("Downloading Statcast %s → %s ...", start, end)
    try:
        import pybaseball
        pybaseball.cache.enable()  # enables local HTTP caching
        df = pybaseball.statcast(start_dt=start, end_dt=end, verbose=False)
    except Exception as e:
        logger.error("Statcast download failed for %d-%02d: %s", year, month, e)
        return pd.DataFrame()

    if df is None or df.empty:
        logger.warning("No statcast data for %d-%02d", year, month)
        df = pd.DataFrame()
    else:
        logger.info("  → %d pitches, %d games", len(df), df["game_pk"].nunique() if "game_pk" in df.columns else 0)

    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache, index=False)
    return df


def load_statcast_season(year: int, force: bool = False) -> pd.DataFrame:
    """
    Load full season of Statcast data (April–October).
    Downloads month-by-month if not cached. Returns combined DataFrame.
    """
    # MLB regular season: April (4) through October (10)
    # Spring training starts March but we skip pre-season
    months = list(range(3, 11))  # Mar–Oct to catch any early openers
    parts: list[pd.DataFrame] = []
    for month in months:
        df = fetch_statcast_month(year, month, force=force)
        if not df.empty:
            parts.append(df)
        time.sleep(0.5)  # be polite to the API

    if not parts:
        logger.warning("No statcast data for season %d", year)
        return pd.DataFrame()

    combined = pd.concat(parts, ignore_index=True)
    # Keep only regular season + postseason game types
    if "game_type" in combined.columns:
        combined = combined[combined["game_type"].isin(["R", "F", "D", "L", "W"])]

    logger.info("Season %d: %d pitches across %d games",
                year, len(combined), combined["game_pk"].nunique() if "game_pk" in combined.columns else 0)
    return combined


# ── Retrosheet game logs (for Elo / pregame priors) ───────────────────────────

def _retrosheet_cache_path(year: int) -> Path:
    return RAW_DATA_DIR / "retrosheet" / f"game_log_{year}.parquet"


def _fetch_retrosheet_direct(year: int) -> pd.DataFrame:
    """
    Download Retrosheet game log directly from retrosheet.org.

    URL:  https://www.retrosheet.org/gamelogs/gl{year}.zip
    File: GL{year}.TXT  (comma-separated, no header, 161 fields)

    Key column positions (0-indexed):
      0  — Date (YYYYMMDD)
      3  — Visiting team abbreviation
      6  — Home team abbreviation
      9  — Visiting team runs scored
      10 — Home team runs scored

    Returns a DataFrame with columns matching the names expected by
    pregame_prior_builder._retrosheet_columns():
      date, v_name, h_name, v_score, h_score
    """
    import io
    import zipfile
    import urllib.request

    url = f"https://www.retrosheet.org/gamelogs/gl{year}.zip"
    logger.info("Downloading Retrosheet game log from %s ...", url)

    req = urllib.request.Request(url, headers={"User-Agent": "mlb_model/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        target = f"GL{year}.TXT"
        names = zf.namelist()
        # case-insensitive match in case zip uses different casing
        match = next((n for n in names if n.upper() == target), None)
        if match is None:
            raise FileNotFoundError(
                f"{target} not found in zip. Contents: {names}"
            )
        raw_csv = zf.read(match).decode("latin-1")

    rows = []
    for line in raw_csv.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) < 11:
            continue
        try:
            rows.append({
                "date": parts[0].strip('"'),
                "v_name": parts[3].strip('"'),
                "h_name": parts[6].strip('"'),
                "v_score": int(parts[9].strip('"')),
                "h_score": int(parts[10].strip('"')),
            })
        except (ValueError, IndexError):
            continue

    df = pd.DataFrame(rows)
    logger.info("  → %d games for %d via direct download", len(df), year)
    return df


def fetch_retrosheet_game_log(year: int, force: bool = False) -> pd.DataFrame:
    """
    Download Retrosheet game log for a season and cache to parquet.
    Contains one row per game: date, home team, away team, home score, away score.

    Uses direct HTTP download from retrosheet.org (pybaseball.retrosheet_game_log
    does not exist in current pybaseball releases and is not used).
    """
    cache = _retrosheet_cache_path(year)
    if cache.exists() and not force:
        logger.info("retrosheet cache hit: %s", cache)
        return pd.read_parquet(cache)

    try:
        df = _fetch_retrosheet_direct(year)
    except Exception as e:
        logger.error(
            "Retrosheet direct download failed for %d: %s — "
            "Elo table will be incomplete for this season.",
            year, e,
        )
        return pd.DataFrame()

    if df is None or df.empty:
        logger.warning("No retrosheet data for %d", year)
        return pd.DataFrame()

    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache, index=False)
    return df


def load_retrosheet_seasons(years: list[int], force: bool = False) -> pd.DataFrame:
    """Load multiple seasons of Retrosheet game logs."""
    parts = []
    for year in years:
        df = fetch_retrosheet_game_log(year, force=force)
        if not df.empty:
            df["season"] = year
            parts.append(df)
        time.sleep(0.3)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Download historical MLB data")
    parser.add_argument("--seasons", nargs="+", type=int, default=[2023, 2024, 2025],
                        help="Seasons to download")
    parser.add_argument("--force", action="store_true", help="Re-download even if cached")
    parser.add_argument("--retrosheet-only", action="store_true",
                        help="Only download Retrosheet game logs (faster, for Elo building)")
    args = parser.parse_args()

    for year in args.seasons:
        if not args.retrosheet_only:
            load_statcast_season(year, force=args.force)
        fetch_retrosheet_game_log(year, force=args.force)

    logger.info("Download complete.")


if __name__ == "__main__":
    main()
