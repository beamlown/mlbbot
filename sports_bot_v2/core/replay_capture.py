"""
replay_capture.py — Capture orderbook + mark + model inputs + decision per discovery loop

Records all inputs and outputs from each loop iteration in JSONL format for offline replay.
One file per day: runtime/replay_captures/YYYY-MM-DD.jsonl
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def write_capture(record: dict) -> None:
    """
    Append a single capture record to the day's JSONL file.

    Record must contain at minimum:
      ts, loop_id, event_slug, registry_match, orderbook, mark,
      model_inputs, model_output, discovery_decision
    """
    try:
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")

        capture_dir = Path("runtime/replay_captures")
        capture_dir.mkdir(parents=True, exist_ok=True)

        capture_file = capture_dir / f"{date_str}.jsonl"

        with open(capture_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        import logging
        logger = logging.getLogger("replay_capture")
        logger.warning("Failed to write capture record: %s", e)
