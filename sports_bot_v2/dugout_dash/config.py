"""dugout_dash config — env-driven."""
from __future__ import annotations
import os
from pathlib import Path


def _env_int(k: str, default: int) -> int:
    try:
        return int(os.getenv(k, default))
    except (TypeError, ValueError):
        return default


def _env_float(k: str, default: float) -> float:
    try:
        return float(os.getenv(k, default))
    except (TypeError, ValueError):
        return default


PORT = _env_int("DUGOUT_DASH_PORT", _env_int("DASHBOARD_PORT", 8900))
HOST = os.getenv("DUGOUT_DASH_HOST", "0.0.0.0")
DB_PATH = os.getenv("DB_PATH", "trades_sports.db")
STATE_PATH = os.getenv("STATE_PATH", "runtime/state.json")
SPORT = os.getenv("SPORT", "baseball")
STARTING_BANKROLL = _env_float("STARTING_BANKROLL", 500.0)

# Tazz: {slug} is replaced with the team display name in lowercase_underscored form,
# e.g. "Colorado Rockies" -> "colorado_rockies". By default we use the home team
# (home broadcast feed). Override TAZZ_TEAM_SIDE=away to follow away team.
TAZZ_BASE_URL = os.getenv("TAZZ_BASE_URL", "https://tazztv.io/?league=MLB&name={slug}")
TAZZ_TEAM_SIDE = os.getenv("TAZZ_TEAM_SIDE", "home")
TAZZ_FORCE_LINK = os.getenv("TAZZ_FORCE_LINK", "0") == "1"
TAZZ_IFRAME_TIMEOUT_MS = _env_int("TAZZ_IFRAME_TIMEOUT_MS", 3000)

# Coalescing
MARK_UPDATE_HZ = _env_float("DUGOUT_MARK_UPDATE_HZ", 5.0)
HOF_CACHE_TTL_SEC = _env_int("DUGOUT_HOF_CACHE_TTL", 60)

# MLB model shadow recs
SHADOW_LOG_PATH = os.getenv(
    "MLB_SHADOW_LOG_PATH",
    str(Path(__file__).resolve().parents[2] / "mlb_model" / "logs" / "shadow_recommendations.jsonl"),
)
