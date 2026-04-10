"""
sports/mlb/team_normalizer.py — Canonical MLB team name normalization

Maps every common form (full name, city, nickname, abbreviation, ESPN display,
Statcast abbreviation, Polymarket phrasing) to a single canonical abbreviation
used in the model's Elo table and feature store.

Public API:
    normalize(name: str) -> str
        Returns 3-letter uppercase team abbreviation, or the input if unknown.

    canonical_full_name(abbrev: str) -> str
        Returns the full display name for a team abbreviation.

    match(a: str, b: str) -> bool
        Returns True if both names resolve to the same team.
"""
from __future__ import annotations

import re

# Map every alias to canonical 3-letter abbreviation (Retrosheet/Statcast style)
_ALIASES: dict[str, str] = {
    # ── Arizona Diamondbacks ──────────────────────────────────────────────────
    "ari": "ARI", "arizona": "ARI", "arizona diamondbacks": "ARI", "diamondbacks": "ARI", "dbacks": "ARI",
    # ── Atlanta Braves ────────────────────────────────────────────────────────
    "atl": "ATL", "atlanta": "ATL", "atlanta braves": "ATL", "braves": "ATL",
    # ── Baltimore Orioles ─────────────────────────────────────────────────────
    "bal": "BAL", "baltimore": "BAL", "baltimore orioles": "BAL", "orioles": "BAL",
    # ── Boston Red Sox ────────────────────────────────────────────────────────
    "bos": "BOS", "boston": "BOS", "boston red sox": "BOS", "red sox": "BOS",
    # ── Chicago Cubs ──────────────────────────────────────────────────────────
    "chc": "CHC", "chicago cubs": "CHC", "cubs": "CHC", "chi cubs": "CHC",
    # ── Chicago White Sox ─────────────────────────────────────────────────────
    "cws": "CWS", "chw": "CWS", "chicago white sox": "CWS", "white sox": "CWS", "chi sox": "CWS",
    # ── Cincinnati Reds ───────────────────────────────────────────────────────
    "cin": "CIN", "cincinnati": "CIN", "cincinnati reds": "CIN", "reds": "CIN",
    # ── Cleveland Guardians ───────────────────────────────────────────────────
    "cle": "CLE", "cleveland": "CLE", "cleveland guardians": "CLE", "guardians": "CLE",
    "cleveland indians": "CLE", "indians": "CLE",  # historical
    # ── Colorado Rockies ──────────────────────────────────────────────────────
    "col": "COL", "colorado": "COL", "colorado rockies": "COL", "rockies": "COL",
    # ── Detroit Tigers ────────────────────────────────────────────────────────
    "det": "DET", "detroit": "DET", "detroit tigers": "DET", "tigers": "DET",
    # ── Houston Astros ────────────────────────────────────────────────────────
    "hou": "HOU", "houston": "HOU", "houston astros": "HOU", "astros": "HOU",
    # ── Kansas City Royals ────────────────────────────────────────────────────
    "kc": "KCR", "kcr": "KCR", "kansas city": "KCR", "kansas city royals": "KCR", "royals": "KCR",
    # ── Los Angeles Angels ────────────────────────────────────────────────────
    "laa": "LAA", "la angels": "LAA", "los angeles angels": "LAA", "angels": "LAA",
    "anaheim angels": "LAA", "ana": "LAA", "cal": "LAA",
    # ── Los Angeles Dodgers ───────────────────────────────────────────────────
    "lad": "LAD", "la dodgers": "LAD", "los angeles dodgers": "LAD", "dodgers": "LAD",
    # ── Miami Marlins ─────────────────────────────────────────────────────────
    "mia": "MIA", "miami": "MIA", "miami marlins": "MIA", "marlins": "MIA",
    "florida marlins": "MIA", "flo": "MIA",
    # ── Milwaukee Brewers ─────────────────────────────────────────────────────
    "mil": "MIL", "milwaukee": "MIL", "milwaukee brewers": "MIL", "brewers": "MIL",
    # ── Minnesota Twins ───────────────────────────────────────────────────────
    "min": "MIN", "minnesota": "MIN", "minnesota twins": "MIN", "twins": "MIN",
    # ── New York Mets ─────────────────────────────────────────────────────────
    "nym": "NYM", "nymets": "NYM", "ny mets": "NYM", "new york mets": "NYM", "mets": "NYM",
    # ── New York Yankees ──────────────────────────────────────────────────────
    "nyy": "NYY", "ny yankees": "NYY", "new york yankees": "NYY", "yankees": "NYY",
    # ── Oakland Athletics ─────────────────────────────────────────────────────
    "oak": "OAK", "oakland": "OAK", "oakland athletics": "OAK", "athletics": "OAK",
    "as": "OAK",  # A's (apostrophe stripped)
    # ── Philadelphia Phillies ─────────────────────────────────────────────────
    "phi": "PHI", "philadelphia": "PHI", "philadelphia phillies": "PHI", "phillies": "PHI",
    # ── Pittsburgh Pirates ────────────────────────────────────────────────────
    "pit": "PIT", "pittsburgh": "PIT", "pittsburgh pirates": "PIT", "pirates": "PIT",
    # ── San Diego Padres ──────────────────────────────────────────────────────
    "sd": "SDP", "sdp": "SDP", "san diego": "SDP", "san diego padres": "SDP", "padres": "SDP",
    # ── San Francisco Giants ──────────────────────────────────────────────────
    "sf": "SFG", "sfg": "SFG", "san francisco": "SFG", "san francisco giants": "SFG", "giants": "SFG",
    # ── Seattle Mariners ──────────────────────────────────────────────────────
    "sea": "SEA", "seattle": "SEA", "seattle mariners": "SEA", "mariners": "SEA",
    # ── St. Louis Cardinals ───────────────────────────────────────────────────
    "stl": "STL", "st louis": "STL", "st. louis": "STL", "st. louis cardinals": "STL",
    "cardinals": "STL", "cards": "STL",
    # ── Tampa Bay Rays ────────────────────────────────────────────────────────
    "tb": "TBR", "tbr": "TBR", "tampa bay": "TBR", "tampa bay rays": "TBR", "rays": "TBR",
    "tampa bay devil rays": "TBR", "tbd": "TBR",
    # ── Texas Rangers ────────────────────────────────────────────────────────
    "tex": "TEX", "texas": "TEX", "texas rangers": "TEX", "rangers": "TEX",
    # ── Toronto Blue Jays ─────────────────────────────────────────────────────
    "tor": "TOR", "toronto": "TOR", "toronto blue jays": "TOR", "blue jays": "TOR",
    # ── Washington Nationals ──────────────────────────────────────────────────
    "wsh": "WSN", "wsn": "WSN", "was": "WSN", "washington": "WSN",
    "washington nationals": "WSN", "nationals": "WSN", "nats": "WSN",
    "montreal expos": "WSN", "expos": "WSN", "mon": "WSN",  # historical
}

_FULL_NAMES: dict[str, str] = {
    "ARI": "Arizona Diamondbacks",
    "ATL": "Atlanta Braves",
    "BAL": "Baltimore Orioles",
    "BOS": "Boston Red Sox",
    "CHC": "Chicago Cubs",
    "CWS": "Chicago White Sox",
    "CIN": "Cincinnati Reds",
    "CLE": "Cleveland Guardians",
    "COL": "Colorado Rockies",
    "DET": "Detroit Tigers",
    "HOU": "Houston Astros",
    "KCR": "Kansas City Royals",
    "LAA": "Los Angeles Angels",
    "LAD": "Los Angeles Dodgers",
    "MIA": "Miami Marlins",
    "MIL": "Milwaukee Brewers",
    "MIN": "Minnesota Twins",
    "NYM": "New York Mets",
    "NYY": "New York Yankees",
    "OAK": "Oakland Athletics",
    "PHI": "Philadelphia Phillies",
    "PIT": "Pittsburgh Pirates",
    "SDP": "San Diego Padres",
    "SFG": "San Francisco Giants",
    "SEA": "Seattle Mariners",
    "STL": "St. Louis Cardinals",
    "TBR": "Tampa Bay Rays",
    "TEX": "Texas Rangers",
    "TOR": "Toronto Blue Jays",
    "WSN": "Washington Nationals",
}


def _clean(name: str) -> str:
    """Lowercase, strip apostrophes and punctuation, collapse whitespace."""
    s = str(name).lower()
    s = s.replace("'", "").replace("\u2019", "")   # apostrophes
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize(name: str) -> str:
    """Return canonical 3-letter abbreviation, or original if unknown."""
    key = _clean(name)
    return _ALIASES.get(key, name.strip().upper())


def canonical_full_name(abbrev: str) -> str:
    """Return full display name for an abbreviation."""
    return _FULL_NAMES.get(abbrev.upper(), abbrev)


def match(a: str, b: str) -> bool:
    """Return True if both names resolve to the same canonical abbreviation."""
    na = normalize(a)
    nb = normalize(b)
    if na == nb:
        return True
    # fallback substring
    ca, cb = _clean(a), _clean(b)
    return ca in cb or cb in ca


def parse_question_teams(question: str) -> "tuple[str, str] | None":
    """
    Parse team names from a Polymarket question string.

    Returns (tracked_team, opponent) where both are canonical abbreviations,
    or None if fewer than two known teams can be identified.

    tracked_team = the team YES pays on (typically mentioned first in the question).

    Examples:
      "Will the Texas Rangers win vs the Baltimore Orioles?"  -> ("TEX", "BAL")
      "Will Rangers beat Orioles?"                            -> ("TEX", "BAL")
      "Will the D-backs beat the Cubs?"                       -> ("ARI", "CHC")
      "Will the A's beat the Mariners?"                       -> ("OAK", "SEA")
      "Texas Rangers vs Baltimore Orioles (Moneyline)"        -> ("TEX", "BAL")
      "MLB: Will CWS top the Yankees?"                        -> ("CWS", "NYY")
    """
    import re as _re

    # Strip common preamble ("MLB:", "MLB -", etc.)
    q = _re.sub(r'^mlb\s*[:\-\u2013]?\s*', '', question.strip(), flags=_re.IGNORECASE)
    # Strip trailing parentheticals like "(April 3, 2026)", "(Game 1)", "(2026)"
    q = _re.sub(r'\s*\([^)]*\)\s*$', '', q).strip()
    # Strip trailing punctuation
    q = _re.sub(r'[\?\.\!]+$', '', q).strip()
    # Strip another parenthetical in case there were two: "... (Apr 3)? (Game 1)"
    q = _re.sub(r'\s*\([^)]*\)\s*$', '', q).strip()

    # Verb-split patterns: each yields (raw_team_a, raw_team_b)
    # team_a is the tracked/YES team (mentioned first)
    verb_patterns = [
        # "Will [the] TEAM_A beat/defeat/top/edge [the] TEAM_B"
        r'will\s+(?:the\s+)?(.+?)\s+(?:beat|defeat|top|edge|down|eliminate)\s+(?:the\s+)?(.+)',
        # "Will [the] TEAM_A win vs/against [the] TEAM_B"
        r'will\s+(?:the\s+)?(.+?)\s+win\s+(?:vs\.?|versus|against)\s+(?:the\s+)?(.+)',
        # "TEAM_A vs/v TEAM_B [moneyline/winner/ml/game N]"
        r'^(?:the\s+)?(.+?)\s+(?:vs\.?|v\.?)\s+(?:the\s+)?(.+?)(?:\s+moneyline|\s+winner|\s+ml|\s+game\s+\d+)?$',
        # "TEAM_A / TEAM_B"  (slash separator)
        r'^(?:the\s+)?(.+?)\s*/\s*(?:the\s+)?(.+)$',
        # "Will the TEAM_A win?" — single team, no opponent → skip (can't pair)
        # handled by returning None via fallback
    ]

    for pat in verb_patterns:
        m = _re.search(pat, q, _re.IGNORECASE)
        if m:
            raw_a = m.group(1).strip().rstrip('.,')
            raw_b = m.group(2).strip().rstrip('.,')
            for prefix in ('the ', 'a '):
                if raw_a.lower().startswith(prefix):
                    raw_a = raw_a[len(prefix):]
                if raw_b.lower().startswith(prefix):
                    raw_b = raw_b[len(prefix):]
            canon_a = normalize(raw_a)
            canon_b = normalize(raw_b)
            if canon_a in _FULL_NAMES and canon_b in _FULL_NAMES and canon_a != canon_b:
                return canon_a, canon_b

    # Fallback: scan left-to-right for the first two distinct known team mentions
    # using progressively shorter n-gram windows (4 words down to 1)
    tokens = _clean(q).split()
    found: list[str] = []
    for width in (4, 3, 2, 1):
        for i in range(len(tokens) - width + 1):
            phrase = " ".join(tokens[i: i + width])
            canon = _ALIASES.get(phrase)
            if canon and canon not in found:
                found.append(canon)
        if len(found) >= 2:
            return found[0], found[1]

    return None
