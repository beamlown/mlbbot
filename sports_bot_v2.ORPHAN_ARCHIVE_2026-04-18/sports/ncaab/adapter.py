"""
sports/ncaab/adapter.py — NCAAB/March Madness sport adapter config
"""
SPORT = "basketball"
TOURNAMENT = "march_madness"
TAG_SLUG = "march-madness"
KEYWORDS = [
    "ncaa", "march madness", "sweet 16", "sweet sixteen",
    "elite 8", "elite eight", "final four", "championship",
    "tournament", "ncaab", "college basketball",
]

from sports.ncaab.live_stats import extract_teams_from_question, get_game_state
from sports.ncaab.signal import game_signal

__all__ = ["SPORT", "TOURNAMENT", "TAG_SLUG", "KEYWORDS", "extract_teams_from_question", "get_game_state", "game_signal"]
