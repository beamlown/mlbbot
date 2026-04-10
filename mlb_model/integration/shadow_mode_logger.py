"""
integration/shadow_mode_logger.py — Shadow mode recommendation logging

Phase 1: Log all recommendations without executing them.
Captures model output alongside market state so you can later compare
what the model said vs what the market resolved to.

Log format (JSONL):
    Each line is a JSON object with:
    - recommendation dict (full to_dict() output)
    - ts: ISO8601 timestamp
    - phase: "shadow" | "advisory" | "merged"

Also supports outcome logging (for backtesting shadow P&L):
    log_outcome(market_id, yes_resolved: bool) → update existing recs with resolution

Usage:
    from integration.shadow_mode_logger import ShadowLogger
    logger_instance = ShadowLogger()
    logger_instance.log(recommendation)
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SHADOW_LOG_PATH = Path(os.getenv("SHADOW_LOG_PATH", "logs/shadow_recommendations.jsonl"))
PHASE = os.getenv("PHASE", "shadow")


class ShadowLogger:
    """
    Logs recommendations and tracks shadow P&L.
    Thread-safe for single-process use.
    """

    def __init__(self, log_path: Path | None = None, phase: str | None = None):
        self.log_path = log_path or SHADOW_LOG_PATH
        self.phase = phase or PHASE
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._pending: dict[str, dict] = {}  # market_id → last recommendation

    def log(self, rec: "Recommendation") -> None:
        """Log a recommendation (regardless of action)."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "phase": self.phase,
            **rec.to_dict(),
        }

        # Track pending recommendations for outcome matching
        self._pending[rec.market_id] = entry

        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.warning("Shadow log write failed: %s", e)

        if rec.action != "NO_TRADE":
            logger.info(
                "[SHADOW] %s %s | fair=%.4f cost=%.4f edge=%.4f | %s vs %s | i=%d %s outs=%d",
                rec.action,
                rec.tracked_team,
                rec.fair_win_prob,
                rec.market_yes_cost if rec.action == "BUY_YES" else rec.market_no_cost,
                rec.edge_yes if rec.action == "BUY_YES" else rec.edge_no,
                rec.home_team,
                rec.away_team,
                rec.inning,
                "BOT" if rec.inning_half else "TOP",
                rec.outs,
            )

    def log_outcome(self, market_id: str, yes_resolved: bool) -> None:
        """
        Log the final market resolution outcome.
        Appends a resolution event to the JSONL log.
        """
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event_type": "outcome",
            "market_id": market_id,
            "yes_resolved": yes_resolved,
        }
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.warning("Outcome log write failed: %s", e)
        self._pending.pop(market_id, None)

    def compute_shadow_pnl(self) -> dict[str, Any]:
        """
        Read the full shadow log and compute hypothetical P&L.
        Matches BUY_YES/BUY_NO recommendations to outcome events.
        Returns summary stats.
        """
        if not self.log_path.exists():
            return {"error": "no shadow log found"}

        recs: dict[str, list[dict]] = {}   # market_id → list of trade-eligible recs
        outcomes: dict[str, bool] = {}     # market_id → yes_resolved

        with open(self.log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if obj.get("event_type") == "outcome":
                    outcomes[obj["market_id"]] = obj["yes_resolved"]
                elif obj.get("action") in ("BUY_YES", "BUY_NO"):
                    mid = obj["market_id"]
                    recs.setdefault(mid, []).append(obj)

        total_recs = sum(len(v) for v in recs.values())
        matched = 0
        wins = 0
        shadow_pnl = 0.0
        total_edge = 0.0

        for mid, rec_list in recs.items():
            if mid not in outcomes:
                continue
            yes_won = outcomes[mid]
            for r in rec_list:
                matched += 1
                action = r["action"]
                edge = r.get("edge_yes" if action == "BUY_YES" else "edge_no", 0.0)
                total_edge += edge
                # Simple P&L: stake = 1 unit, payoff = 1 / ask - 1
                ask = r.get("ask_yes" if action == "BUY_YES" else "ask_no") or 0.5
                won = (action == "BUY_YES" and yes_won) or (action == "BUY_NO" and not yes_won)
                if won:
                    wins += 1
                    shadow_pnl += (1.0 / ask - 1.0)
                else:
                    shadow_pnl -= 1.0

        return {
            "total_recommendations": total_recs,
            "actionable_recs": matched,
            "resolved": len(outcomes),
            "win_rate": wins / matched if matched > 0 else 0.0,
            "shadow_pnl_units": round(shadow_pnl, 4),
            "avg_edge": round(total_edge / matched, 6) if matched > 0 else 0.0,
        }


# ── Module-level convenience instance ─────────────────────────────────────────
_default_logger: ShadowLogger | None = None


def get_logger() -> ShadowLogger:
    global _default_logger
    if _default_logger is None:
        _default_logger = ShadowLogger()
    return _default_logger
