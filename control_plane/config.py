"""Runtime configuration for the control plane.

All paths resolve relative to the repo root so the package is location-
independent. Env vars override every default.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    # control_plane/config.py → parents[1] is the repo root
    return Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    bridge_root: Path
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
        data_dir = Path(os.environ.get("CONTROL_PLANE_DATA_DIR", repo / "control_plane" / "data"))
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "runs").mkdir(parents=True, exist_ok=True)
        return cls(
            repo_root=repo,
            bridge_root=bridge,
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
