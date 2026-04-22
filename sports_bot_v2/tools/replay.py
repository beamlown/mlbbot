#!/usr/bin/env python3
"""
tools/replay.py — Minimal CLI for counterfactual replay analysis

Run historical captures through alternate guard rail configurations to assess
model calibration and gate effectiveness.

Usage:
  python tools/replay.py --start 2026-04-18 --end 2026-04-18
  python tools/replay.py --start 2026-04-18 --end 2026-04-20 --confidence 0.65 --edge 2.0
  python tools/replay.py --start 2026-04-18 --end 2026-04-18 --json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

# Make sports_bot_v2/ root importable
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.replay_harness import (
    replay,
    ReplayConfig,
    SizingCurve,
)


def parse_date(s: str) -> date:
    """Parse YYYY-MM-DD string to date."""
    dt = datetime.fromisoformat(s)
    return dt.date()


def format_result(result, json_out: bool = False) -> str:
    """Format a ReplayResult for display."""
    if json_out:
        # Serialize to JSON
        data = {
            "config": {
                "name": result.config.name,
                "confidence_gate": result.config.confidence_gate,
                "edge_threshold_pct": result.config.edge_threshold_pct,
                "slippage_cents": result.config.slippage_cents,
                "model_version": result.config.model_version,
            },
            "summary": {
                "n_trades": result.n_trades,
                "n_skipped": result.n_skipped,
                "hit_rate": round(result.hit_rate, 4),
                "total_pnl": round(result.total_pnl, 2),
                "brier_score": round(result.brier_score, 4),
                "log_loss": round(result.log_loss, 4),
                "expected_edge_realized_pct": round(result.expected_edge_realized_pct, 2),
            },
            "pnl_by_trade_class": {
                cls: round(pnl, 2) for cls, pnl in result.pnl_by_trade_class.items()
            },
        }
        return json.dumps(data, indent=2)
    else:
        # Text format
        lines = [
            "=" * 66,
            f"REPLAY HARNESS — {result.config.name.upper()}",
            "=" * 66,
            f"Config: confidence_gate={result.config.confidence_gate}, edge_threshold={result.config.edge_threshold_pct}%",
            f"Trades evaluated: {result.n_trades}  (skipped: {result.n_skipped})",
            f"Hit rate: {result.hit_rate:.2%}",
            f"Total PnL: ${result.total_pnl:.2f}",
            f"Brier score: {result.brier_score:.4f}",
            f"Expected edge realized: {result.expected_edge_realized_pct:.2f}%",
        ]

        if result.pnl_by_trade_class:
            lines.append("PnL by trade class:")
            for cls, pnl in sorted(result.pnl_by_trade_class.items()):
                lines.append(f"  {cls}: ${pnl:.2f}")

        lines.append("=" * 66)
        return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Replay historical captures through alternate guardrail configs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "--start",
        required=True,
        type=str,
        help="Start date (YYYY-MM-DD)",
    )
    ap.add_argument(
        "--end",
        required=True,
        type=str,
        help="End date (YYYY-MM-DD)",
    )
    ap.add_argument(
        "--confidence",
        type=float,
        default=0.60,
        help="Minimum confidence to trade (default: 0.60)",
    )
    ap.add_argument(
        "--edge",
        type=float,
        default=1.0,
        help="Minimum edge threshold %% (default: 1.0)",
    )
    ap.add_argument(
        "--slippage",
        type=float,
        default=2.0,
        help="Slippage in cents (default: 2.0)",
    )
    ap.add_argument(
        "--json",
        dest="json_out",
        action="store_true",
        help="Output results as JSON",
    )
    ap.add_argument(
        "--name",
        type=str,
        default="replay",
        help="Name for this replay config",
    )
    ap.add_argument(
        "--captures-dir",
        type=Path,
        default=Path("runtime/replay_captures"),
        help="Path to capture directory",
    )

    args = ap.parse_args()

    # Parse dates
    start = parse_date(args.start)
    end = parse_date(args.end)

    # Create captures_dir as absolute if relative
    captures_dir = args.captures_dir
    if not captures_dir.is_absolute():
        captures_dir = Path(_ROOT) / captures_dir

    # Create config
    sizing = SizingCurve()
    config = ReplayConfig(
        name=args.name,
        confidence_gate=args.confidence,
        edge_threshold_pct=args.edge,
        sizing=sizing,
        slippage_cents=args.slippage,
    )

    # Run replay
    result = replay(captures_dir, start, end, config)

    # Output
    print(format_result(result, json_out=args.json_out))


if __name__ == "__main__":
    main()
