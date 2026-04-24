"""Runtime configuration for the control plane.

All paths resolve relative to the repo root so the package is location-
independent. Env vars override every default.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    # control_plane/config.py → parents[1] is the repo root
    return Path(__file__).resolve().parents[1]


# Canonical anchor: legacy BOT_BRIDGE is frozen after this timestamp.
# Any file under legacy_bridge_root with mtime > this refuses boot.
_DEFAULT_LEGACY_CUTOFF = datetime(2026, 4, 18, 0, 0, 0, tzinfo=timezone.utc).timestamp()


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    bridge_root: Path
    bot_source_root: Path
    legacy_bridge_root: Path
    legacy_cutoff_ts: float
    archive_after_days: int
    orphan_source_globs: tuple[str, ...]
    force_start: bool
    data_dir: Path
    db_path: Path
    runs_dir: Path
    host: str
    port: int
    debug: bool
    default_role: str
    claude_bin: str

    @classmethod
    def load(cls) -> "Settings":
        repo = Path(os.environ.get("CONTROL_PLANE_REPO_ROOT", _repo_root()))
        bridge = Path(os.environ.get("CONTROL_PLANE_BRIDGE_ROOT", repo / "BOT_BRIDGE"))
        bot_source = Path(os.environ.get(
            "CONTROL_PLANE_BOT_SOURCE_ROOT",
            r"C:\Users\johnny\Desktop\sports_bot_v2",
        ))
        legacy_bridge = Path(os.environ.get(
            "CONTROL_PLANE_LEGACY_BRIDGE_ROOT",
            r"C:\Users\johnny\Desktop\BOT_BRIDGE",
        ))
        cutoff_ts = float(os.environ.get(
            "CONTROL_PLANE_LEGACY_CUTOFF_TS",
            str(_DEFAULT_LEGACY_CUTOFF),
        ))
        archive_days = int(os.environ.get("CONTROL_PLANE_ARCHIVE_AFTER_DAYS", "14"))
        data_dir = Path(os.environ.get("CONTROL_PLANE_DATA_DIR", repo / "control_plane" / "data"))
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "runs").mkdir(parents=True, exist_ok=True)
        return cls(
            repo_root=repo,
            bridge_root=bridge,
            bot_source_root=bot_source,
            legacy_bridge_root=legacy_bridge,
            legacy_cutoff_ts=cutoff_ts,
            archive_after_days=archive_days,
            orphan_source_globs=(
                r"C:\Users\johnny\Desktop\mlbbot\sports_bot_v2",
                r"C:\Users\johnny\Desktop\mlbbot\sports_bot_v2.ORPHAN_ARCHIVE_*",
            ),
            force_start=os.environ.get("CONTROL_PLANE_FORCE_START", "0") == "1",
            data_dir=data_dir,
            db_path=Path(os.environ.get("CONTROL_PLANE_DB", data_dir / "control_plane.db")),
            runs_dir=data_dir / "runs",
            host=os.environ.get("CONTROL_PLANE_HOST", "127.0.0.1"),
            port=int(os.environ.get("CONTROL_PLANE_PORT", "8787")),
            debug=os.environ.get("CONTROL_PLANE_DEBUG", "0") == "1",
            default_role=os.environ.get("CONTROL_PLANE_DEFAULT_ROLE", "SONNET_MANAGER"),
            claude_bin=os.environ.get("CONTROL_PLANE_CLAUDE_BIN", "claude"),
        )


SETTINGS: Settings = Settings.load()
