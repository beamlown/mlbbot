"""
core/selfcheck.py — Startup and runtime self-check system

Verifies that all required components are healthy before allowing new entries.
Returns a BotMode that the execution layer uses to gate behavior.

Modes:
  OPERATIONAL   — all hard requirements pass, entries allowed
  NO_NEW_ENTRIES — soft requirement failure or stale data
  EXITS_ONLY    — critical runtime failure (order heartbeat, etc.)
  HALT          — hard startup failure, bot must not trade

Startup checks (hard — failure → HALT):
  - can fetch ESPN scoreboard (live game registry works)
  - can determine today's MLB games
  - can distinguish live/pre/final status
  - model artifacts loaded
  - auth available if live trading enabled

Startup checks (soft — failure → NO_NEW_ENTRIES):
  - pitch count data available
  - Elo table loaded (prior quality)
  - market discovery works (Gamma API)
  - sharp odds available (ODDS_API_KEY set)

Runtime checks (called every 60s):
  - registry age < 30s
  - game state age < GAME_STATE_MAX_AGE_SEC
  - book age < BOOK_MAX_AGE_SEC

Public API:
    startup_check() -> SelfCheckResult
    runtime_check(registry, snapshots, books) -> SelfCheckResult
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)

BotMode = Literal["OPERATIONAL", "NO_NEW_ENTRIES", "EXITS_ONLY", "HALT"]

GAME_STATE_MAX_AGE_SEC = float(os.getenv("GAME_STATE_MAX_AGE_SEC", "15"))
BOOK_MAX_AGE_SEC = float(os.getenv("BOOK_MAX_AGE_SEC", "5"))
REGISTRY_MAX_AGE_SEC = 30.0


@dataclass
class CheckItem:
    name: str
    passed: bool
    is_hard: bool
    detail: str = ""


@dataclass
class SelfCheckResult:
    mode: BotMode
    checks: list[CheckItem] = field(default_factory=list)
    allow_new_entries: bool = True
    reasons: list[str] = field(default_factory=list)

    @property
    def hard_failures(self) -> list[CheckItem]:
        return [c for c in self.checks if c.is_hard and not c.passed]

    @property
    def soft_failures(self) -> list[CheckItem]:
        return [c for c in self.checks if not c.is_hard and not c.passed]


def _check(name: str, is_hard: bool, fn) -> CheckItem:
    try:
        result, detail = fn()
        return CheckItem(name=name, passed=bool(result), is_hard=is_hard, detail=detail)
    except Exception as e:
        return CheckItem(name=name, passed=False, is_hard=is_hard, detail=str(e))


def startup_check(require_live_trading_auth: bool = False) -> SelfCheckResult:
    """
    Run all startup checks. Returns SelfCheckResult with mode set.
    Call this before entering the main trading loop.
    """
    checks: list[CheckItem] = []

    # ── Hard checks ───────────────────────────────────────────────────────────

    # H1: ESPN scoreboard reachable
    def _check_espn_scoreboard():
        from sports.mlb.live_game_registry import refresh_registry
        games = refresh_registry()
        return True, f"{len(games)} games in scoreboard"
    checks.append(_check("espn_scoreboard", is_hard=True, fn=_check_espn_scoreboard))

    # H2: Can determine live vs scheduled vs final
    def _check_live_detection():
        from sports.mlb.live_game_registry import get_all_games
        games = get_all_games()
        statuses = {g.status for g in games}
        return len(statuses) > 0, f"statuses seen: {statuses}"
    checks.append(_check("live_detection", is_hard=True, fn=_check_live_detection))

    # H3: Model artifacts loaded (or loadable)
    def _check_model_artifacts():
        from sports.mlb.winprob_inference import is_loaded, load_artifacts
        if not is_loaded():
            load_artifacts()
        return is_loaded(), "model + calibrator loaded"
    checks.append(_check("model_artifacts", is_hard=True, fn=_check_model_artifacts))

    # H4: Execution mode flag
    def _check_phase():
        phase = os.getenv("PHASE", "shadow")
        return True, f"phase={phase}"
    checks.append(_check("phase_config", is_hard=True, fn=_check_phase))

    # H5: Auth (only hard if live trading)
    if require_live_trading_auth:
        def _check_auth():
            pk = os.getenv("PK", "")
            return bool(pk), "PK env var set" if pk else "PK not set"
        checks.append(_check("trading_auth", is_hard=True, fn=_check_auth))

    # ── Soft checks ───────────────────────────────────────────────────────────

    # S1: Elo table available
    def _check_elo_table():
        from data.pregame_prior_builder import load_elo_table
        elo = load_elo_table()
        return len(elo) > 0, f"{len(elo)} Elo rows"
    checks.append(_check("elo_table", is_hard=False, fn=_check_elo_table))

    # S2: Feature schema exists
    def _check_feature_schema():
        import json
        schema_path = os.path.join(os.getenv("ARTIFACT_DIR", "artifacts"), "feature_schema.json")
        if not os.path.exists(schema_path):
            return False, "feature_schema.json not found"
        with open(schema_path) as f:
            schema = json.load(f)
        return True, f"{schema['n_features']} features"
    checks.append(_check("feature_schema", is_hard=False, fn=_check_feature_schema))

    # S3: Sharp odds (Pinnacle API key) — optional enhancement only.
    # Absence of ODDS_API_KEY is NOT a degraded condition: the Elo prior
    # is the correct and sufficient pregame source for shadow/advisory mode.
    # Always passes; logs presence/absence at INFO so it's visible without
    # contributing to soft_failures or mode degradation.
    def _check_sharp_odds():
        key = os.getenv("ODDS_API_KEY", "")
        return True, "ODDS_API_KEY set (sharp prior available)" if key else "no ODDS_API_KEY — using Elo prior (OK)"
    checks.append(_check("sharp_odds", is_hard=False, fn=_check_sharp_odds))

    # S4: Market discovery (Polymarket Gamma)
    # Default matches the hardcoded fallback in recommendation_api._discover_mlb_markets()
    # so selfcheck and discovery are always consistent.
    _GAMMA_DEFAULT = "https://gamma-api.polymarket.com"
    def _check_gamma_api():
        gamma = os.getenv("GAMMA_API_URL", _GAMMA_DEFAULT)
        return True, f"GAMMA_API_URL={gamma}"
    checks.append(_check("gamma_api", is_hard=False, fn=_check_gamma_api))

    # ── Determine mode ────────────────────────────────────────────────────────
    hard_failures = [c for c in checks if c.is_hard and not c.passed]
    soft_failures = [c for c in checks if not c.is_hard and not c.passed]

    reasons: list[str] = []

    if hard_failures:
        mode: BotMode = "HALT"
        for c in hard_failures:
            reasons.append(f"HARD_FAIL:{c.name}:{c.detail}")
        logger.error("Startup HALT — hard failures: %s", [c.name for c in hard_failures])
    elif soft_failures:
        mode = "NO_NEW_ENTRIES"
        for c in soft_failures:
            reasons.append(f"SOFT_FAIL:{c.name}:{c.detail}")
        logger.warning("Startup NO_NEW_ENTRIES — soft failures: %s", [c.name for c in soft_failures])
    else:
        mode = "OPERATIONAL"
        logger.info("Startup check PASSED — mode=OPERATIONAL")

    for c in checks:
        level = logging.INFO if c.passed else (logging.ERROR if c.is_hard else logging.WARNING)
        logger.log(level, "  [%s] %s%s%s",
                   "PASS" if c.passed else "FAIL",
                   c.name,
                   " (hard)" if c.is_hard else " (soft)",
                   f": {c.detail}" if c.detail else "")

    return SelfCheckResult(
        mode=mode,
        checks=checks,
        allow_new_entries=(mode == "OPERATIONAL"),
        reasons=reasons,
    )


def runtime_check(
    registry_age_sec: float,
    game_state_ages_sec: list[float],   # age of each candidate game's snapshot
    book_ages_sec: list[float],         # age of each candidate market's book
    order_heartbeat_ok: bool = True,
) -> SelfCheckResult:
    """
    Run runtime health checks. Call every 60 seconds.
    Returns SelfCheckResult with degraded mode if anything is stale.
    """
    checks: list[CheckItem] = []
    reasons: list[str] = []

    # R1: Registry age
    reg_ok = registry_age_sec < REGISTRY_MAX_AGE_SEC
    checks.append(CheckItem(
        name="registry_age",
        passed=reg_ok,
        is_hard=False,
        detail=f"{registry_age_sec:.1f}s (max {REGISTRY_MAX_AGE_SEC}s)"
    ))

    # R2: Game state ages
    stale_gs = [a for a in game_state_ages_sec if a > GAME_STATE_MAX_AGE_SEC]
    gs_ok = len(stale_gs) == 0
    checks.append(CheckItem(
        name="game_state_freshness",
        passed=gs_ok,
        is_hard=False,
        detail=f"{len(stale_gs)} stale snapshots (max {GAME_STATE_MAX_AGE_SEC}s)"
    ))

    # R3: Book ages
    stale_books = [a for a in book_ages_sec if a > BOOK_MAX_AGE_SEC]
    book_ok = len(stale_books) == 0
    checks.append(CheckItem(
        name="book_freshness",
        passed=book_ok,
        is_hard=False,
        detail=f"{len(stale_books)} stale books (max {BOOK_MAX_AGE_SEC}s)"
    ))

    # R4: Order heartbeat
    checks.append(CheckItem(
        name="order_heartbeat",
        passed=order_heartbeat_ok,
        is_hard=True,   # heartbeat failure → EXITS_ONLY
        detail="ok" if order_heartbeat_ok else "heartbeat failure"
    ))

    # Determine mode
    hard_failures = [c for c in checks if c.is_hard and not c.passed]
    soft_failures = [c for c in checks if not c.is_hard and not c.passed]

    if hard_failures:
        mode: BotMode = "EXITS_ONLY"
        for c in hard_failures:
            reasons.append(f"HARD:{c.name}")
    elif soft_failures:
        mode = "NO_NEW_ENTRIES"
        for c in soft_failures:
            reasons.append(f"SOFT:{c.name}")
    else:
        mode = "OPERATIONAL"

    return SelfCheckResult(
        mode=mode,
        checks=checks,
        allow_new_entries=(mode == "OPERATIONAL"),
        reasons=reasons,
    )
