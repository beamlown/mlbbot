"""
sports/mlb/adapter.py — MLB sport adapter config
"""
import re

SPORT = "baseball"
TOURNAMENT = "mlb"
TAG_SLUG = "mlb"
KEYWORDS = [
    "mlb", "major league baseball", "baseball",
    "world series", "alcs", "nlcs", "alds", "nlds",
]

# Only per-game events: mlb-pit-cin-2026-03-31, mlb-lad-sf-2026-03-31, etc.
GAME_EVENT_RE = re.compile(r'^mlb-[a-z]+-[a-z]+-\d{4}-\d{2}-\d{2}$')

from sports.mlb.live_stats import extract_teams_from_question, get_game_state
from sports.mlb.signal import game_signal

__all__ = ["SPORT", "TOURNAMENT", "TAG_SLUG", "KEYWORDS", "GAME_EVENT_RE", "extract_teams_from_question", "get_game_state", "game_signal"]
