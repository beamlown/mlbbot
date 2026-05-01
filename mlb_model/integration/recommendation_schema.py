"""
integration/recommendation_schema.py — Recommendation output schema

The canonical object that the MLB model produces and the execution bot consumes.
This schema is the contract between the two systems.

Both systems must agree on this schema. Any breaking change requires
a version bump in model_version.

The existing bot (sports_bot_v2) should consume this object and apply its
own execution gates before trading. It must NOT apply its own probability
estimates when a valid Recommendation is present — the model is the
decision authority; the bot is the execution authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ACTION = Literal["BUY_YES", "BUY_NO", "NO_TRADE"]
SIZE_TIER = Literal["normal", "strong", "none"]


@dataclass
class Recommendation:
    """
    MLB win probability trade recommendation.

    The existing bot should:
      1. Check action != "NO_TRADE"
      2. Apply freshness / liquidity / risk / auth gates
      3. Execute if all gates pass
      4. Log recommendation with outcome for shadow mode analysis
    """
    # ── Market identification ─────────────────────────────────────────────────
    market_id: str              # Polymarket condition/market ID
    yes_token_id: str           # Polymarket YES token
    no_token_id: str            # Polymarket NO token
    market_slug: str            # e.g. "will-the-texas-rangers-win-vs-the-baltimore-orioles"

    # ── Teams ─────────────────────────────────────────────────────────────────
    home_team: str              # canonical abbreviation
    away_team: str
    tracked_team: str           # team this YES contract pays on
    is_home_team: bool          # is tracked team the home team?

    # ── Model output ─────────────────────────────────────────────────────────
    fair_win_prob: float        # calibrated P(tracked_team wins)
    p_home: float               # calibrated P(home wins)
    pregame_win_prob: float     # Elo prior

    # ── Market state at signal time ───────────────────────────────────────────
    market_yes_cost: float      # ask_yes + fee + slippage
    market_no_cost: float       # ask_no + fee + slippage
    ask_yes: float | None
    ask_no: float | None
    spread: float | None
    thin_side_depth_usd: float

    # ── Edge calculation ──────────────────────────────────────────────────────
    edge_yes: float             # fair_win_prob - market_yes_cost
    edge_no: float              # (1 - fair_win_prob) - market_no_cost

    # ── Decision ─────────────────────────────────────────────────────────────
    action: ACTION              # "BUY_YES" | "BUY_NO" | "NO_TRADE"
    size_tier: SIZE_TIER        # "normal" (edge≥0.05) | "strong" (edge≥0.08) | "none"
    size_mult: float            # position size multiplier (1.0 = normal, 1.5 = strong)
    tp_price: float | None = None  # take-profit price (if model-issued)
    sl_price: float | None = None  # stop-loss price (if model-issued)
    recommended_size_dollars: float | None = None  # model-recommended position size in USD
    recommended_size_units: float | None = None    # model-recommended position size in units

    # ── Model metadata ────────────────────────────────────────────────────────
    model_version: str = "mlb_winprob_v1"  # e.g. "mlb_winprob_v1_lgbm"
    data_quality: float = 0.0   # 0-1 confidence in feature completeness
    confidence: float = 0.0     # normalized 0-1 (derived from edge and quality)
    reasons: list[str] = field(default_factory=list)

    # ── Game state snapshot ───────────────────────────────────────────────────
    inning: int = 0
    inning_half: int = 0        # 0=top, 1=bottom
    outs: int = 0
    score_diff: int = 0         # home_score - away_score
    game_progress: float = 0.0
    game_status: str = ""       # EARLY_INNINGS | MID_GAME | LATE_GAME | EXTRAS

    # ── Timestamps ────────────────────────────────────────────────────────────
    feature_timestamp: str = ""        # ISO8601 when features were computed
    game_state_timestamp: str = ""     # ISO8601 when game state was fetched
    book_timestamp: str = ""           # ISO8601 when order book was fetched
    game_state_age_sec: float = 0.0
    book_age_sec: float = 0.0

    def to_dict(self) -> dict:
        """Serialize to the canonical JSON format expected by the execution bot."""
        return {
            "market_id": self.market_id,
            "yes_token_id": self.yes_token_id,
            "no_token_id": self.no_token_id,
            "market_slug": self.market_slug,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "tracked_team": self.tracked_team,
            "is_home_team": self.is_home_team,
            "fair_win_prob": self.fair_win_prob,
            "p_home": self.p_home,
            "pregame_win_prob": self.pregame_win_prob,
            "market_yes_cost": self.market_yes_cost,
            "market_no_cost": self.market_no_cost,
            "ask_yes": self.ask_yes,
            "ask_no": self.ask_no,
            "spread": self.spread,
            "thin_side_depth_usd": self.thin_side_depth_usd,
            "edge_yes": self.edge_yes,
            "edge_no": self.edge_no,
            "action": self.action,
            "size_tier": self.size_tier,
            "size_mult": self.size_mult,
            "tp_price": self.tp_price,
            "sl_price": self.sl_price,
            "recommended_size_dollars": self.recommended_size_dollars,
            "recommended_size_units": self.recommended_size_units,
            "model_version": self.model_version,
            "data_quality": self.data_quality,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "inning": self.inning,
            "inning_half": self.inning_half,
            "outs": self.outs,
            "score_diff": self.score_diff,
            "game_progress": self.game_progress,
            "game_status": self.game_status,
            "feature_timestamp": self.feature_timestamp,
            "game_state_timestamp": self.game_state_timestamp,
            "book_timestamp": self.book_timestamp,
            "game_state_age_sec": self.game_state_age_sec,
            "book_age_sec": self.book_age_sec,
        }

    @classmethod
    def no_trade(
        cls,
        market_id: str,
        reason: str,
        **kwargs,
    ) -> "Recommendation":
        """Create a NO_TRADE recommendation with a reason."""
        return cls(
            market_id=market_id,
            yes_token_id=kwargs.get("yes_token_id", ""),
            no_token_id=kwargs.get("no_token_id", ""),
            market_slug=kwargs.get("market_slug", ""),
            home_team=kwargs.get("home_team", ""),
            away_team=kwargs.get("away_team", ""),
            tracked_team=kwargs.get("tracked_team", ""),
            is_home_team=kwargs.get("is_home_team", True),
            fair_win_prob=kwargs.get("fair_win_prob", 0.5),
            p_home=kwargs.get("p_home", 0.5),
            pregame_win_prob=kwargs.get("pregame_win_prob", 0.54),
            market_yes_cost=kwargs.get("market_yes_cost", 1.0),
            market_no_cost=kwargs.get("market_no_cost", 1.0),
            ask_yes=None,
            ask_no=None,
            spread=None,
            thin_side_depth_usd=0.0,
            edge_yes=0.0,
            edge_no=0.0,
            action="NO_TRADE",
            size_tier="none",
            size_mult=0.0,
            model_version=kwargs.get("model_version", "mlb_winprob_v1"),
            data_quality=0.0,
            confidence=0.0,
            reasons=[reason],
            feature_timestamp=kwargs.get("feature_timestamp", ""),
        )
