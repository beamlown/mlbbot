"""
backfill_season.py — Reusable MLB season backfill script.

Fills missing game_date partitions in the canonical MLB raw/normalized store.
Idempotency rule: skip any game_date partition that already has a file in
raw/games/game_date=YYYY-MM-DD/. Only write new dates.

Usage:
    python backfill_season.py [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]

Defaults:
    --start-date  2026-03-25  (Opening Day 2026)
    --end-date    yesterday
"""

import argparse
import json
import time
from datetime import date, timedelta
from pathlib import Path
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://statsapi.mlb.com/api/v1"
SEASON = 2026
CANONICAL_ROOT = Path(
    r"C:\Users\johnny\Desktop\mlb_model\data\foundation\mlb_statsapi\season=2026"
)
RAW_ROOT = CANONICAL_ROOT / "raw"
NORM_ROOT = CANONICAL_ROOT / "normalized"
MANIFESTS_ROOT = CANONICAL_ROOT / "manifests"

# Polite inter-game delay (seconds)
INTER_GAME_SLEEP = 0.15


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def date_range(start: date, end: date):
    """Yield each date from start to end inclusive."""
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def parse_date(s: str) -> date:
    return date.fromisoformat(s)


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "mlbbot-backfill/1.0"})


def api_get(path: str, params: dict | None = None) -> dict:
    url = BASE_URL + path
    resp = SESSION.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_schedule(start: date, end: date) -> list[dict]:
    """
    Return a flat list of completed regular-season game dicts from the schedule.
    Each dict has: gamePk, officialDate, gameDate (ISO UTC), teams, venue, status.
    """
    data = api_get(
        "/schedule",
        params={
            "sportId": 1,
            "season": SEASON,
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "gameType": "R",
        },
    )
    games = []
    for date_entry in data.get("dates", []):
        for g in date_entry.get("games", []):
            games.append(g)
    return games


def fetch_boxscore(game_pk: int) -> dict:
    return api_get(f"/game/{game_pk}/boxscore")


def fetch_linescore(game_pk: int) -> dict:
    return api_get(f"/game/{game_pk}/linescore")


def fetch_teams() -> list[dict]:
    data = api_get("/teams", params={"sportId": 1, "season": SEASON})
    return data.get("teams", [])


# ---------------------------------------------------------------------------
# Idempotency check
# ---------------------------------------------------------------------------

def partition_exists(entity: str, game_date: str) -> bool:
    """Return True if ANY file exists for this entity + game_date partition."""
    part_dir = RAW_ROOT / entity / f"game_date={game_date}"
    if not part_dir.exists():
        return False
    return any(part_dir.iterdir())


def teams_partition_exists() -> bool:
    part_dir = RAW_ROOT / "teams" / "game_date=season"
    if not part_dir.exists():
        return False
    return any(part_dir.iterdir())


# ---------------------------------------------------------------------------
# JSONL write helper
# ---------------------------------------------------------------------------

def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


# ---------------------------------------------------------------------------
# Raw entity builders
# ---------------------------------------------------------------------------

def build_raw_game(g: dict, game_date: str) -> dict:
    """
    Build a raw game record from a schedule game dict + augmented from boxscore.
    g must already have been enriched with boxscore data for abbrs.
    """
    teams = g["teams"]
    home = teams["home"]
    away = teams["away"]

    home_team_id = home["team"]["id"]
    away_team_id = away["team"]["id"]

    # Determine winner/loser
    winner_team_id = None
    loser_team_id = None
    if home.get("isWinner"):
        winner_team_id = home_team_id
        loser_team_id = away_team_id
    elif away.get("isWinner"):
        winner_team_id = away_team_id
        loser_team_id = home_team_id
    # else: tie — leave null

    return {
        "game_pk": g["gamePk"],
        "game_date": game_date,
        "season": SEASON,
        "status": g["status"]["detailedState"],
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "home_team_abbr": g.get("_home_abbr"),
        "away_team_abbr": g.get("_away_abbr"),
        "home_score": home.get("score"),
        "away_score": away.get("score"),
        "winner_team_id": winner_team_id,
        "loser_team_id": loser_team_id,
        "venue_id": g.get("venue", {}).get("id"),
        "start_time_utc": g.get("gameDate"),   # already ISO UTC e.g. "2026-04-12T17:35:00Z"
        "end_time_utc": None,
    }


def build_pitcher_game_logs(game_pk: int, game_date: str, boxscore: dict) -> list[dict]:
    """One record per pitcher per game from boxscore."""
    logs = []
    for side in ("home", "away"):
        team_data = boxscore["teams"][side]
        team_id = team_data["team"]["id"]
        pitcher_ids = team_data.get("pitchers", [])
        players = team_data.get("players", {})

        for idx, pid in enumerate(pitcher_ids):
            key = f"ID{pid}"
            p = players.get(key, {})
            pitching = p.get("stats", {}).get("pitching", {})
            if not pitching:
                continue

            is_starter = bool(pitching.get("gamesStarted", 0))

            logs.append({
                "game_pk": game_pk,
                "game_date": game_date,
                "pitcher_id": pid,
                "team_id": team_id,
                "is_starting_pitcher": is_starter,
                "innings_pitched": pitching.get("inningsPitched"),
                "hits_allowed": pitching.get("hits"),
                "runs_allowed": pitching.get("runs"),
                "earned_runs": pitching.get("earnedRuns"),
                "walks": pitching.get("baseOnBalls"),
                "strikeouts": pitching.get("strikeOuts"),
                "pitches_thrown": pitching.get("pitchesThrown"),
            })
    return logs


def _ip_str_to_float(ip_str) -> float:
    """
    Convert innings-pitched string like '5.2' to a float the same way the
    original backfill did: simple float() conversion.
    e.g. '5.2' -> 5.2, NOT 5.667
    This preserves the existing floating-point quirk in the data.
    """
    if ip_str is None:
        return 0.0
    try:
        return float(ip_str)
    except (ValueError, TypeError):
        return 0.0


def build_team_game_logs(
    game_pk: int,
    game_date: str,
    schedule_game: dict,
    boxscore: dict,
    pitcher_logs: list[dict],
) -> list[dict]:
    """One record per team per game."""
    logs = []
    for side, opp_side in (("home", "away"), ("away", "home")):
        team_data = boxscore["teams"][side]
        opp_data = boxscore["teams"][opp_side]
        team_id = team_data["team"]["id"]
        opp_team_id = opp_data["team"]["id"]

        is_home = side == "home"

        sched_side = schedule_game["teams"][side]
        sched_opp = schedule_game["teams"][opp_side]
        runs_scored = sched_side.get("score", 0)
        runs_allowed = sched_opp.get("score", 0)

        batting_stats = team_data.get("teamStats", {}).get("batting", {})
        fielding_stats = team_data.get("teamStats", {}).get("fielding", {})
        hits = batting_stats.get("hits")
        errors = fielding_stats.get("errors")

        win_flag = bool(sched_side.get("isWinner", False))

        # Find starting pitcher for this team from pitcher_logs
        starting_pitcher_id = None
        for pl in pitcher_logs:
            if pl["team_id"] == team_id and pl["is_starting_pitcher"]:
                starting_pitcher_id = pl["pitcher_id"]
                break

        # Bullpen: sum all non-starter pitchers' innings and runs
        bullpen_innings = 0.0
        bullpen_runs_allowed = 0
        for pl in pitcher_logs:
            if pl["team_id"] == team_id and not pl["is_starting_pitcher"]:
                bullpen_innings += _ip_str_to_float(pl["innings_pitched"])
                bullpen_runs_allowed += (pl["runs_allowed"] or 0)

        logs.append({
            "game_pk": game_pk,
            "game_date": game_date,
            "team_id": team_id,
            "opponent_team_id": opp_team_id,
            "is_home": is_home,
            "runs_scored": runs_scored,
            "runs_allowed": runs_allowed,
            "hits": hits,
            "errors": errors,
            "win_flag": win_flag,
            "starting_pitcher_id": starting_pitcher_id,
            "bullpen_innings": bullpen_innings,
            "bullpen_runs_allowed": bullpen_runs_allowed,
        })
    return logs


def build_bullpen_context(
    game_pk: int,
    game_date: str,
    boxscore: dict,
    pitcher_logs: list[dict],
) -> list[dict]:
    """One record per team per game for bullpen context."""
    records = []
    for side in ("home", "away"):
        team_data = boxscore["teams"][side]
        team_id = team_data["team"]["id"]

        # Bullpen pitchers are non-starters
        bullpen_pids = [
            p_id for p_id in team_data.get("pitchers", [])
            if not any(
                pl["pitcher_id"] == p_id and pl["team_id"] == team_id and pl["is_starting_pitcher"]
                for pl in pitcher_logs
            )
        ]
        bullpen_pitchers_used = len(bullpen_pids)

        bullpen_innings = 0.0
        bullpen_runs_allowed = 0
        bullpen_pitch_count = 0

        players = team_data.get("players", {})
        for pid in bullpen_pids:
            key = f"ID{pid}"
            p = players.get(key, {})
            pitching = p.get("stats", {}).get("pitching", {})
            if not pitching:
                continue
            bullpen_innings += _ip_str_to_float(pitching.get("inningsPitched"))
            bullpen_runs_allowed += (pitching.get("runs") or 0)
            bullpen_pitch_count += (pitching.get("pitchesThrown") or 0)

        records.append({
            "game_pk": game_pk,
            "game_date": game_date,
            "team_id": team_id,
            "bullpen_pitchers_used": bullpen_pitchers_used,
            "bullpen_innings": bullpen_innings,
            "bullpen_runs_allowed": bullpen_runs_allowed,
            "bullpen_pitch_count": bullpen_pitch_count,
        })
    return records


def build_game_state_history(
    game_pk: int,
    game_date: str,
    boxscore: dict,
    linescore: dict,
) -> list[dict]:
    """
    Build inning-half state history from linescore innings array.
    Matches existing shape: outs/base_state/event_ts are null (linescore-only).

    Convention (matches existing data from prior backfill):
    - Each inning produces two rows (top and bottom).
    - home_score = home team's runs scored in this inning (home_half.get("runs")).
    - away_score = away team's runs scored in this inning (away_half.get("runs")).
    - Both top and bottom rows for the same inning carry the same home_score/away_score.
    - If a half-inning was not played (e.g. walk-off), the run value is null (key absent).
    """
    home_team_id = boxscore["teams"]["home"]["team"]["id"]
    away_team_id = boxscore["teams"]["away"]["team"]["id"]

    records = []
    innings = linescore.get("innings", [])

    for inning_data in innings:
        inning_num = inning_data["num"]

        home_half = inning_data.get("home", {})
        away_half = inning_data.get("away", {})

        # home_score/away_score use .get("runs") — returns None if key absent (not played)
        home_runs = home_half.get("runs")
        away_runs = away_half.get("runs")

        # Top half (away bats)
        records.append({
            "game_pk": game_pk,
            "game_date": game_date,
            "inning": inning_num,
            "inning_half": "top",
            "outs": None,
            "home_score": home_runs,
            "away_score": away_runs,
            "batting_team_id": away_team_id,
            "pitching_team_id": home_team_id,
            "base_state": None,
            "event_ts": None,
        })

        # Bottom half (home bats)
        records.append({
            "game_pk": game_pk,
            "game_date": game_date,
            "inning": inning_num,
            "inning_half": "bottom",
            "outs": None,
            "home_score": home_runs,
            "away_score": away_runs,
            "batting_team_id": home_team_id,
            "pitching_team_id": away_team_id,
            "base_state": None,
            "event_ts": None,
        })

    return records


def build_raw_teams(teams_api: list[dict]) -> list[dict]:
    records = []
    for t in teams_api:
        league = t.get("league", {}).get("name")
        division = t.get("division", {}).get("name")
        records.append({
            "team_id": t["id"],
            "team_abbr": t.get("abbreviation"),
            "team_name": t.get("name"),
            "league": league,
            "division": division,
        })
    return records


# ---------------------------------------------------------------------------
# Normalized layer builders
# ---------------------------------------------------------------------------

def build_normalized_game(raw_game: dict) -> dict:
    """Normalized games == raw games (same shape)."""
    return dict(raw_game)


def build_normalized_team_game_log(raw_log: dict) -> dict:
    """
    Normalized team_game_log: matches existing shape where
    starting_pitcher_id, bullpen_innings, bullpen_runs_allowed are null.
    This is the observed shape from the prior backfill.
    """
    return {
        "game_pk": raw_log["game_pk"],
        "game_date": raw_log["game_date"],
        "team_id": raw_log["team_id"],
        "opponent_team_id": raw_log["opponent_team_id"],
        "is_home": raw_log["is_home"],
        "runs_scored": raw_log["runs_scored"],
        "runs_allowed": raw_log["runs_allowed"],
        "hits": raw_log["hits"],
        "errors": raw_log["errors"],
        "win_flag": raw_log["win_flag"],
        "starting_pitcher_id": None,
        "bullpen_innings": None,
        "bullpen_runs_allowed": None,
    }


def build_normalized_pitcher_game_log(raw_log: dict) -> dict:
    """Normalized pitcher_game_log == raw (same shape)."""
    return dict(raw_log)


def build_normalized_game_state_feature(raw_rec: dict) -> dict:
    """Normalized game_state_feature == raw game_state_history (same shape)."""
    return dict(raw_rec)


# ---------------------------------------------------------------------------
# Main per-date writer
# ---------------------------------------------------------------------------

def process_date(
    game_date_str: str,
    schedule_games: list[dict],
    counts: dict,
) -> bool:
    """
    Process all completed games for a single game_date.
    Returns True if data was written, False if skipped.
    """
    # Idempotency: skip if games partition already exists
    if partition_exists("games", game_date_str):
        print(f"  SKIP {game_date_str} — partition already exists")
        return False

    print(f"  PROCESS {game_date_str} — {len(schedule_games)} games")

    raw_games = []
    raw_tgl = []
    raw_pgl = []
    raw_bc = []
    raw_gsh = []

    norm_games = []
    norm_tgl = []
    norm_pgl = []
    norm_gsf = []

    for g in schedule_games:
        game_pk = g["gamePk"]
        print(f"    Fetching game {game_pk}...", end=" ", flush=True)

        try:
            boxscore = fetch_boxscore(game_pk)
            linescore = fetch_linescore(game_pk)
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        # Enrich schedule game with abbreviations from boxscore
        g["_home_abbr"] = boxscore["teams"]["home"]["team"].get("abbreviation")
        g["_away_abbr"] = boxscore["teams"]["away"]["team"].get("abbreviation")

        # Raw entities
        game_rec = build_raw_game(g, game_date_str)
        pitcher_logs = build_pitcher_game_logs(game_pk, game_date_str, boxscore)
        team_logs = build_team_game_logs(game_pk, game_date_str, g, boxscore, pitcher_logs)
        bullpen = build_bullpen_context(game_pk, game_date_str, boxscore, pitcher_logs)
        gsh = build_game_state_history(game_pk, game_date_str, boxscore, linescore)

        raw_games.append(game_rec)
        raw_pgl.extend(pitcher_logs)
        raw_tgl.extend(team_logs)
        raw_bc.extend(bullpen)
        raw_gsh.extend(gsh)

        # Normalized
        norm_games.append(build_normalized_game(game_rec))
        norm_tgl.extend(build_normalized_team_game_log(tl) for tl in team_logs)
        norm_pgl.extend(build_normalized_pitcher_game_log(pl) for pl in pitcher_logs)
        norm_gsf.extend(build_normalized_game_state_feature(r) for r in gsh)

        print(f"ok ({len(pitcher_logs)} pitchers, {len(gsh)} state rows)")
        time.sleep(INTER_GAME_SLEEP)

    if not raw_games:
        print(f"    No completed games written for {game_date_str}")
        return False

    # Write raw partitions
    part = f"game_date={game_date_str}"
    write_jsonl(RAW_ROOT / "games" / part / "games.jsonl", raw_games)
    write_jsonl(RAW_ROOT / "team_game_logs" / part / "team_game_logs.jsonl", raw_tgl)
    write_jsonl(RAW_ROOT / "pitcher_game_logs" / part / "pitcher_game_logs.jsonl", raw_pgl)
    write_jsonl(RAW_ROOT / "bullpen_context" / part / "bullpen_context.jsonl", raw_bc)
    write_jsonl(RAW_ROOT / "game_state_history" / part / "game_state_history.jsonl", raw_gsh)

    # Write normalized partitions
    write_jsonl(NORM_ROOT / "games" / part / "games.jsonl", norm_games)
    write_jsonl(NORM_ROOT / "team_game_logs" / part / "team_game_logs.jsonl", norm_tgl)
    write_jsonl(NORM_ROOT / "pitcher_game_logs" / part / "pitcher_game_logs.jsonl", norm_pgl)
    write_jsonl(NORM_ROOT / "game_state_features" / part / "game_state_features.jsonl", norm_gsf)

    counts["games"] += len(raw_games)
    counts["team_game_logs"] += len(raw_tgl)
    counts["pitcher_game_logs"] += len(raw_pgl)
    counts["bullpen_context"] += len(raw_bc)
    counts["game_state_history"] += len(raw_gsh)
    counts["normalized_games"] += len(norm_games)
    counts["normalized_team_game_logs"] += len(norm_tgl)
    counts["normalized_pitcher_game_logs"] += len(norm_pgl)
    counts["normalized_game_state_features"] += len(norm_gsf)

    print(
        f"    Wrote {game_date_str}: {len(raw_games)} games, "
        f"{len(raw_pgl)} pitcher logs, {len(raw_gsh)} state rows"
    )
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="MLB season backfill")
    parser.add_argument(
        "--start-date",
        default="2026-03-25",
        help="Start date YYYY-MM-DD (default: 2026-03-25)",
    )
    parser.add_argument(
        "--end-date",
        default=(date.today() - timedelta(days=1)).isoformat(),
        help="End date YYYY-MM-DD (default: yesterday)",
    )
    args = parser.parse_args()

    start = parse_date(args.start_date)
    end = parse_date(args.end_date)
    today = date.today()

    # Safety: never process today (may be in-progress)
    if end >= today:
        end = today - timedelta(days=1)
        print(f"[backfill] Clamped end date to {end} (never process today)")

    print(f"[backfill] Date window: {start} to {end}")

    # Write teams if not present
    if not teams_partition_exists():
        print("[backfill] Fetching teams...")
        teams_api = fetch_teams()
        teams_records = build_raw_teams(teams_api)
        teams_path = RAW_ROOT / "teams" / "game_date=season" / "teams.jsonl"
        write_jsonl(teams_path, teams_records)
        print(f"[backfill] Wrote {len(teams_records)} teams")
    else:
        print("[backfill] Teams partition exists — skipping")

    # Fetch full schedule for range
    print(f"[backfill] Fetching schedule {start} to {end}...")
    all_games = fetch_schedule(start, end)
    print(f"[backfill] Schedule returned {len(all_games)} total games")

    # Group by officialDate, filter to Final only
    games_by_date: dict[str, list[dict]] = {}
    for g in all_games:
        gdate = g.get("officialDate") or g.get("gameDate", "")[:10]
        status = g.get("status", {}).get("abstractGameState", "")
        if status != "Final":
            continue
        games_by_date.setdefault(gdate, []).append(g)

    # Process each date
    counts: dict = {
        "games": 0,
        "team_game_logs": 0,
        "pitcher_game_logs": 0,
        "bullpen_context": 0,
        "game_state_history": 0,
        "normalized_games": 0,
        "normalized_team_game_logs": 0,
        "normalized_pitcher_game_logs": 0,
        "normalized_game_state_features": 0,
    }

    processed_dates = []
    skipped_dates = []
    source_unavailable = []

    for d in date_range(start, end):
        d_str = d.isoformat()
        games_for_date = games_by_date.get(d_str, [])

        if not games_for_date:
            # Check if it's a known scheduled date with no Final games
            print(f"  NOTE {d_str} — no Final games in schedule (rest day or postponed)")
            source_unavailable.append(d_str)
            continue

        wrote = process_date(d_str, games_for_date, counts)
        if wrote:
            processed_dates.append(d_str)
        else:
            skipped_dates.append(d_str)

    # Write manifest
    run_ts = datetime.now(timezone.utc).isoformat()
    manifest = {
        "load_type": "backfill",
        "season": SEASON,
        "source_api": "MLB Stats API",
        "run_ts": run_ts,
        "status": "success",
        "date_window": {
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "entities_written": counts,
        "processed_dates": processed_dates,
        "skipped_dates": skipped_dates,
        "source_unavailable": source_unavailable,
    }

    today_str = today.strftime("%Y%m%d")
    manifest_path = MANIFESTS_ROOT / f"backfill_{today_str}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n[backfill] Manifest written: {manifest_path}")
    print(f"[backfill] Processed dates: {processed_dates}")
    print(f"[backfill] Skipped dates:   {skipped_dates}")
    print(f"[backfill] Entity counts (new): {counts}")
    print("[backfill] Done.")


if __name__ == "__main__":
    main()
