"""
core/types.py — shared dataclasses for sports_bot_v2
Extended from march_madness_bot mm_types.py to support multiple sports.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Market:
    market_id: str
    event_slug: str
    slug: str
    question: str
    yes_token_id: str
    no_token_id: str
    start_iso: str | None
    end_iso: str | None
    sport: str          # "basketball" | "baseball"
    tournament: str     # "march_madness" | "mlb" | etc.
    yes_price: float | None = None
    no_price: float | None = None
    volume24h: float | None = None
    active: bool = True
    closed: bool = False
    resolved: bool = False
    market_type: str = "moneyline"   # "moneyline" | "spread" | "total" | "other"
    spread_line: float | None = None
    total_line: float | None = None


@dataclass
class OBSnapshot:
    bid_yes: float | None
    ask_yes: float | None
    bid_no: float | None
    ask_no: float | None
    spread_yes: float | None
    spread_no: float | None
    depth_top5_usd_yes: float
    depth_top5_usd_no: float
    imbalance: float          # (yes_depth - no_depth) / (yes_depth + no_depth + 1e-9)
    micro_ok: bool
    micro_reason: str         # "" when ok; "spread_too_wide"|"depth_too_low"|"stale_data"|"empty_book"
    fetched_at: str = ""
    bid_levels_yes: list[dict] = field(default_factory=list)  # [{"price": x, "size": y}, ...]
    ask_levels_yes: list[dict] = field(default_factory=list)
    bid_levels_no: list[dict] = field(default_factory=list)
    ask_levels_no: list[dict] = field(default_factory=list)


@dataclass
class GameState:
    # ── Universal fields ────────────────────────────────────────────────────
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    # For NCAAB: 1=first half, 2=second half, 3+=OT
    # For MLB: current inning number (1-9+)
    period: int
    clock: str                # NCAAB: "12:34". MLB: "" (no game clock)
    # NCAAB: "PRE_GAME"|"FIRST_HALF"|"HALFTIME"|"SECOND_HALF"|"OVERTIME"|"FINAL"|"unknown"
    # MLB:   "PRE_GAME"|"EARLY_INNINGS"|"MID_GAME"|"LATE_GAME"|"EXTRAS"|"FINAL"|"unknown"
    status: str
    scoring_run_team: str     # team name or ""
    scoring_run_pts: int      # size of run, 0 if none
    last_5min_diff: int       # score diff change in last 5 min / last half inning
    halftime_adj: float       # adjustment signal from half/midgame break
    espn_event_id: str = ""
    fetched_at: str = ""
    sport: str = "basketball" # "basketball" | "baseball"

    # ── NCAAB-specific (ignored for MLB) ───────────────────────────────────
    home_fouls: int = 0
    away_fouls: int = 0
    home_timeouts: int = -1   # -1 = unknown
    away_timeouts: int = -1
    possession: str = ""      # "home" | "away" | ""
    last_play: str = ""
    is_timeout: bool = False
    in_bonus: str = ""        # "home" | "away" | "both" | ""

    # ── MLB-specific (ignored for NCAAB) ───────────────────────────────────
    inning: int = 0            # current inning 1-9+
    inning_half: str = ""      # "top" | "bottom"
    outs: int = 0              # 0-2
    balls: int = 0
    strikes: int = 0
    runners_on: str = ""       # "" | "1B" | "1B,3B" | "loaded" etc.
    home_pitcher: str = ""     # current pitcher display name
    away_pitcher: str = ""
    home_pitcher_pitches: int = 0   # pitches thrown this game
    away_pitcher_pitches: int = 0
    home_errors: int = 0
    away_errors: int = 0
    # Pre-game enrichment from MLB Stats API (player_stats.py)
    home_pitcher_era5: float = 0.0   # ERA over last 5 starts
    away_pitcher_era5: float = 0.0
    home_team_ops7: float = 0.0      # team OPS last 7 days
    away_team_ops7: float = 0.0
    home_bullpen_used: int = 0       # relievers used this game
    away_bullpen_used: int = 0


@dataclass
class Signal:
    side: str                 # "BUY_YES" | "BUY_NO" | "NONE"
    confidence: float         # 0.0 – 1.0
    fair_value_estimate: float
    components: dict[str, Any] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


@dataclass
class Trade:
    id: int | None
    ts_open: str
    ts_close: str | None
    market_slug: str
    market_id: str
    side: str
    qty: float
    entry_px: float
    exit_px: float | None
    pnl_usd: float | None
    fees_usd: float | None
    reason_open: str
    reason_close: str | None
    confidence: float
    mode: str
    status: str               # "open" | "closed"
    source: str = "bot"
    actual_fill_px: float | None = None  # entry price reflecting real walk-the-book + slippage


@dataclass
class ModeCtx:
    mode: str                 # "conservative" | "neutral" | "aggressive"
    score: float
    dwell_trades: int
    profile_multipliers: dict[str, float]
    switch_reason: str
