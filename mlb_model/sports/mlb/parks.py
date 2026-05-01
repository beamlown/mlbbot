"""
sports/mlb/parks.py — Static MLB team-abbreviation → retrosheet ParkID map.

Used by data/state_snapshot_builder.py to label each snapshot's park_id so the
phase-1 enrichment can join to data/features/park_factors.parquet (which is
keyed on retrosheet ParkIDs).

Best-effort 2026 mapping. If a team relocates mid-season, update this map and
re-run the snapshot builder. Unknown teams resolve to "unknown" → live park
factor lookup falls back to neutral 1.0.
"""
from __future__ import annotations

TEAM_TO_PARK: dict[str, str] = {
    # AL East
    "BAL": "BAL12",   # Camden Yards
    "BOS": "BOS07",   # Fenway Park
    "NYY": "NYC21",   # Yankee Stadium (current)
    "TBR": "STP01",   # Tropicana Field
    "TB":  "STP01",
    "TOR": "TOR02",   # Rogers Centre

    # AL Central
    "CHW": "CHI12",   # Guaranteed Rate / Rate Field
    "CWS": "CHI12",
    "CLE": "CLE08",   # Progressive Field
    "DET": "DET05",   # Comerica Park
    "KCR": "KAN06",   # Kauffman Stadium
    "KC":  "KAN06",
    "MIN": "MIN04",   # Target Field

    # AL West
    "ATH": "OAK01",   # Athletics — Oakland Coliseum (placeholder; mid-2025+ moves to Sacramento)
    "OAK": "OAK01",
    "HOU": "HOU03",   # Minute Maid / Daikin Park
    "LAA": "ANA01",   # Angel Stadium
    "SEA": "SEA03",   # T-Mobile Park
    "TEX": "ARL02",   # Globe Life Field

    # NL East
    "ATL": "ATL03",   # Truist Park
    "MIA": "MIA02",   # loanDepot park
    "NYM": "NYC20",   # Citi Field
    "PHI": "PHI13",   # Citizens Bank Park
    "WSH": "WAS11",   # Nationals Park
    "WAS": "WAS11",

    # NL Central
    "CHC": "CHI11",   # Wrigley Field
    "CIN": "CIN09",   # Great American Ball Park
    "MIL": "MIL06",   # American Family Field
    "PIT": "PIT08",   # PNC Park
    "STL": "STL10",   # Busch Stadium

    # NL West
    "ARI": "PHO01",   # Chase Field
    "AZ":  "PHO01",   # Arizona — Statcast uses 'AZ' as the team abbrev
    "COL": "DEN02",   # Coors Field
    "LAD": "LOS03",   # Dodger Stadium
    "SDP": "SAN02",   # Petco Park
    "SD":  "SAN02",
    "SFG": "SFO03",   # Oracle Park
    "SF":  "SFO03",
}

ALL_TEAMS: list[str] = [
    "BAL", "BOS", "NYY", "TBR", "TOR",
    "CHW", "CLE", "DET", "KCR", "MIN",
    "ATH", "HOU", "LAA", "SEA", "TEX",
    "ATL", "MIA", "NYM", "PHI", "WSH",
    "CHC", "CIN", "MIL", "PIT", "STL",
    "ARI", "COL", "LAD", "SDP", "SFG",
]


def lookup_park_id(team_abbrev: str) -> str:
    """Return retrosheet ParkID for a team. 'unknown' if not in map."""
    if not team_abbrev:
        return "unknown"
    return TEAM_TO_PARK.get(team_abbrev.upper(), "unknown")
