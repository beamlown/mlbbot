"""
core/attribution.py — Trade attribution schema and JSONL writer for audit records
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Literal

ExitReason = Literal["TP", "SL", "RESOLUTION", "MANUAL", "SESSION_CAP", "COOLDOWN"]
TradeClass = Literal[
    "MODEL_WIN_EXPECTED", "MODEL_WIN_LUCKY",
    "MODEL_LOSS_EXPECTED", "MODEL_LOSS_EXECUTION",
    "UNRESOLVED",
]

ATTRIBUTION_VERSION = 1


@dataclass
class TradeAttribution:
    trade_id: str
    entry_model_prob: float | None
    entry_market_prob: float | None
    expected_edge_pct: float | None
    actual_fill_px: float | None
    actual_fill_size: float | None
    exit_reason: ExitReason | None
    exit_model_prob: float | None
    exit_market_prob: float | None
    hold_seconds: int | None
    resolved_winner: str | None
    model_side_was_right: bool | None
    realized_pnl: float | None
    trade_class: TradeClass | None
    attribution_version: int = ATTRIBUTION_VERSION


def classify_trade(
    *,
    model_side_was_right: bool | None,
    expected_edge_pct: float | None,
    exit_reason: ExitReason | None,
    realized_pnl: float | None,
) -> TradeClass:
    """
    Classify a trade into one of 5 categories based on model accuracy and edge.

    MODEL_WIN_EXPECTED: model was right, expected_edge_pct > 0 at entry
    MODEL_WIN_LUCKY: model was right but expected_edge_pct <= 0 at entry
    MODEL_LOSS_EXPECTED: model was wrong, expected_edge_pct <= 0 at entry
    MODEL_LOSS_EXECUTION: model was right directionally but we lost P&L
    UNRESOLVED: trade closed without market resolution
    """
    # Trade with no market resolution yet
    if exit_reason in ("MANUAL", "SESSION_CAP", "COOLDOWN") or model_side_was_right is None:
        return "UNRESOLVED"

    # Market was resolved, check if model was right
    if model_side_was_right:
        # Model called it correctly
        if expected_edge_pct is not None and expected_edge_pct > 0:
            return "MODEL_WIN_EXPECTED"
        else:
            return "MODEL_WIN_LUCKY"
    else:
        # Model was wrong on the outcome
        if realized_pnl is not None and realized_pnl > 0:
            # Somehow made money despite being wrong (execution edge)
            return "MODEL_LOSS_EXECUTION"
        elif expected_edge_pct is not None and expected_edge_pct <= 0:
            # We shouldn't have traded (bad expected value)
            return "MODEL_LOSS_EXPECTED"
        else:
            # Model was wrong but we had positive edge at entry (bad luck/market moved)
            return "MODEL_LOSS_EXECUTION"


def write_jsonl(record: TradeAttribution, path: Path) -> None:
    """
    Append a trade attribution record to a JSONL file.
    Each line is a JSON object with an ISO-8601 UTC timestamp wrapper.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert dataclass to dict, excluding None values
    record_dict = asdict(record)

    # Create envelope with timestamp
    envelope = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "record": record_dict,
    }

    # Append as a single JSON line
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(envelope, separators=(",", ":")) + "\n")
