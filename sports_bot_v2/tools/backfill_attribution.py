"""
tools/backfill_attribution.py — Backfill attribution columns for existing trades.

Usage:
    python -m tools.backfill_attribution [--dry-run]

Reads existing trades with NULL attribution columns and attempts to reconstruct
values from logs and DB. Sets attribution_version=0 for best-effort (incomplete)
reconstructions and attribution_version=1 for fully reconstructed trades.
Idempotent: only backfills trades with NULLs.
"""
import argparse
import json
import logging
import sqlite3
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

DB_PATH = os.getenv("DB_PATH", "trades_sports.db")
TRADE_FORENSICS_LOG = "logs/trade_forensics_baseball.jsonl"
OB_SNAPSHOTS_DIR = "runtime/ob_snapshots"


def load_forensics() -> dict[int, dict]:
    """Load trade forensics by trade_id."""
    forensics = {}
    for pattern in ["logs/trade_forensics_baseball.jsonl", "logs/trade_forensics_basketball.jsonl"]:
        log_path = Path(pattern)
        if not log_path.exists():
            continue
        try:
            with open(log_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        tid = obj.get("trade_id")
                        if tid:
                            forensics[tid] = obj
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.warning("Error loading forensics from %s: %s", pattern, e)
    return forensics


def fetch_trades_needing_attribution() -> list[dict]:
    """Fetch all trades with NULL attribution fields (idempotent check)."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM trades
            WHERE (entry_model_prob IS NULL
                   OR entry_market_prob IS NULL
                   OR exit_reason IS NULL
                   OR trade_class IS NULL)
               AND status = 'closed'
            ORDER BY id ASC
        """)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error("Error fetching trades: %s", e)
        return []


def backfill_trade(trade: dict, forensics: dict[int, dict], dry_run: bool) -> dict[str, Any]:
    """
    Attempt to backfill attribution for a single trade.
    Returns: {trade_id, status, filled_fields, version}
    """
    trade_id = trade["id"]
    filled_fields = []
    version = 0

    entry_model_prob = trade.get("entry_model_prob")
    entry_market_prob = trade.get("entry_market_prob")
    expected_edge_pct = trade.get("expected_edge_pct")
    exit_reason = trade.get("exit_reason")
    resolved_winner = trade.get("resolved_winner")
    model_side_was_right = trade.get("model_side_was_right")
    trade_class = trade.get("trade_class")

    # Backfill entry attribution from forensics
    if entry_model_prob is None and trade_id in forensics:
        f = forensics[trade_id]
        if f.get("confidence"):
            entry_model_prob = float(f["confidence"])
            filled_fields.append("entry_model_prob")

    if entry_market_prob is None and trade.get("actual_fill_px"):
        entry_market_prob = float(trade["actual_fill_px"])
        filled_fields.append("entry_market_prob")

    # Compute expected_edge_pct if we have both
    if expected_edge_pct is None and entry_model_prob is not None and entry_market_prob is not None:
        try:
            expected_edge_pct = (float(entry_model_prob) - float(entry_market_prob)) * 100.0
            filled_fields.append("expected_edge_pct")
        except (TypeError, ValueError):
            pass

    # Map reason_close to exit_reason
    if exit_reason is None and trade.get("reason_close"):
        reason_map = {
            "market_resolved": "RESOLUTION",
            "take_profit": "TP",
            "stop_loss": "SL",
            "near_resolution": "RESOLUTION",
            "session_cap": "SESSION_CAP",
            "cooldown": "COOLDOWN",
        }
        exit_reason = reason_map.get(trade["reason_close"], "MANUAL")
        filled_fields.append("exit_reason")

    # Infer resolved_winner and model_side_was_right from exit_px
    if resolved_winner is None and trade.get("exit_px") is not None:
        exit_px = float(trade["exit_px"])
        if exit_px >= 0.99:
            resolved_winner = "YES" if trade["side"] == "BUY_YES" else "NO"
            model_side_was_right = True
            filled_fields.append("resolved_winner")
            filled_fields.append("model_side_was_right")
        elif exit_px <= 0.01:
            resolved_winner = "NO" if trade["side"] == "BUY_YES" else "YES"
            model_side_was_right = False
            filled_fields.append("resolved_winner")
            filled_fields.append("model_side_was_right")

    # Classify trade
    if trade_class is None:
        if resolved_winner is not None and model_side_was_right is not None:
            # We have resolution info, can classify properly
            if model_side_was_right:
                if expected_edge_pct is not None and expected_edge_pct > 0:
                    trade_class = "MODEL_WIN_EXPECTED"
                else:
                    trade_class = "MODEL_WIN_LUCKY"
            else:
                realized_pnl = trade.get("pnl_usd")
                if realized_pnl is not None and realized_pnl > 0:
                    trade_class = "MODEL_LOSS_EXECUTION"
                elif expected_edge_pct is not None and expected_edge_pct <= 0:
                    trade_class = "MODEL_LOSS_EXPECTED"
                else:
                    trade_class = "MODEL_LOSS_EXECUTION"
        else:
            # No resolution, classify as UNRESOLVED
            trade_class = "UNRESOLVED"
        filled_fields.append("trade_class")

    # Determine version: 1 if reliable, 0 if best-effort
    if len(filled_fields) >= 5:
        version = 1
    elif len(filled_fields) > 0:
        version = 0
    else:
        version = 0

    status = "ok" if len(filled_fields) > 0 else "skipped"
    result = {
        "trade_id": trade_id,
        "status": status,
        "filled_fields": filled_fields,
        "version": version,
    }

    if not dry_run and len(filled_fields) > 0:
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5.0)
            updates = {}
            if entry_model_prob is not None:
                updates["entry_model_prob"] = entry_model_prob
            if entry_market_prob is not None:
                updates["entry_market_prob"] = entry_market_prob
            if expected_edge_pct is not None:
                updates["expected_edge_pct"] = expected_edge_pct
            if exit_reason is not None:
                updates["exit_reason"] = exit_reason
            if resolved_winner is not None:
                updates["resolved_winner"] = resolved_winner
            if model_side_was_right is not None:
                updates["model_side_was_right"] = 1 if model_side_was_right else 0
            if trade_class is not None:
                updates["trade_class"] = trade_class
            updates["attribution_version"] = version

            cols = ", ".join([f"{k}=?" for k in updates.keys()])
            vals = list(updates.values()) + [trade_id]
            sql = f"UPDATE trades SET {cols} WHERE id=?"
            conn.execute(sql, vals)
            conn.commit()
            conn.close()
            result["persisted"] = True
        except Exception as e:
            logger.error("Failed to update trade %d: %s", trade_id, e)
            result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser(description="Backfill attribution columns for existing trades")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    args = parser.parse_args()

    logger.info("Loading trade forensics...")
    forensics = load_forensics()
    logger.info("Loaded forensics for %d trades", len(forensics))

    logger.info("Fetching trades needing attribution...")
    trades_to_backfill = fetch_trades_needing_attribution()
    logger.info("Found %d closed trades needing backfill", len(trades_to_backfill))

    if args.dry_run:
        logger.info("DRY RUN MODE — no changes will be written")

    existing_count = len(trades_to_backfill)
    backfilled_count = 0
    unreconstructible_count = 0

    for trade in trades_to_backfill:
        result = backfill_trade(trade, forensics, args.dry_run)
        if result["status"] == "ok":
            backfilled_count += 1
            logger.info(
                "Backfill trade=%d version=%d fields=%s",
                result["trade_id"], result["version"], result["filled_fields"],
            )
        elif result["status"] == "skipped":
            unreconstructible_count += 1

    logger.info("=" * 60)
    logger.info("Backfill summary:")
    logger.info("  Existing closed trades needing backfill: %d", existing_count)
    logger.info("  Backfilled successfully: %d", backfilled_count)
    logger.info("  Skipped (no null fields): %d", unreconstructible_count)
    logger.info("  Dry run: %s", args.dry_run)
    logger.info("=" * 60)

    return {
        "existing_trades_count": existing_count,
        "backfilled_count": backfilled_count,
        "unreconstructible_count": unreconstructible_count,
    }


if __name__ == "__main__":
    main()
