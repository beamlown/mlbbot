"""Resolve the `claude` CLI binary across Windows / macOS / Linux.

Priority order:
  1. Operator override stored in `settings.claude_bin` (editable from /system).
  2. Env var `CONTROL_PLANE_CLAUDE_BIN`.
  3. `shutil.which("claude")` — honours Windows PATHEXT so `claude.cmd` is found.
  4. A list of known install locations for each platform (npm global bin,
     /opt/node22, /usr/local/bin, ~/.local/bin, …).

The resolver is pure — it never mutates the DB. Writing the override goes
through `set_override()` so the `settings` row is updated with a stamp.

For Windows, `.cmd` and `.bat` files can't be executed directly by
`subprocess.Popen` without a shell. `wrap_for_platform()` prepends
`cmd.exe /c` when needed so argv stays a plain list.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ENV_VAR = "CONTROL_PLANE_CLAUDE_BIN"
DB_KEY = "claude_bin"


@dataclass
class Resolved:
    path: str | None
    source: str                    # "db" | "env" | "path" | "builtin" | None
    candidates_tried: list[str]
    version: str | None = None     # populated by probe()
    ok: bool = False
    error: str | None = None


def _windows_candidates() -> list[str]:
    home = Path.home()
    appdata = os.environ.get("APPDATA") or str(home / "AppData" / "Roaming")
    localapp = os.environ.get("LOCALAPPDATA") or str(home / "AppData" / "Local")
    out = [
        str(Path(appdata) / "npm" / "claude.cmd"),
        str(Path(appdata) / "npm" / "claude.exe"),
        str(Path(appdata) / "npm" / "claude"),
        str(Path(localapp) / "Programs" / "claude" / "claude.exe"),
        str(Path(localapp) / "claude" / "claude.exe"),
        r"C:\Program Files\nodejs\claude.cmd",
        r"C:\Program Files\nodejs\claude.exe",
        str(home / "AppData" / "Roaming" / "npm" / "claude.cmd"),
    ]
    # de-dup while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for c in out:
        if c not in seen:
            seen.add(c)
            deduped.append(c)
    return deduped


def _posix_candidates() -> list[str]:
    home = Path.home()
    return [
        "/opt/node22/bin/claude",
        "/usr/local/bin/claude",
        "/usr/bin/claude",
        str(home / ".local" / "bin" / "claude"),
        str(home / ".npm-global" / "bin" / "claude"),
        str(home / ".nvm" / "versions" / "node" / "*" / "bin" / "claude"),
    ]


def _candidates() -> list[str]:
    if platform.system() == "Windows":
        return _windows_candidates()
    return _posix_candidates()


def resolve(db_override: str | None = None) -> Resolved:
    """Return the best candidate path for the `claude` CLI."""
    tried: list[str] = []

    def _try(p: str | None, source: str) -> Resolved | None:
        if not p:
            return None
        tried.append(p)
        return Resolved(path=p, source=source, candidates_tried=tried) if Path(p).is_file() else None

    hit = _try(db_override, "db")
    if hit:
        return hit

    hit = _try(os.environ.get(ENV_VAR), "env")
    if hit:
        return hit

    # shutil.which handles Windows PATHEXT (.CMD/.EXE) automatically.
    for name in ("claude", "claude.cmd", "claude.exe"):
        w = shutil.which(name)
        tried.append(f"which({name})={w}")
        if w and Path(w).is_file():
            return Resolved(path=w, source="path", candidates_tried=tried)

    for c in _candidates():
        hit = _try(c, "builtin")
        if hit:
            return hit

    return Resolved(path=None, source="none", candidates_tried=tried,
                    ok=False, error="no claude binary found")


def wrap_for_platform(binpath: str, args: list[str]) -> list[str]:
    """On Windows, `.cmd` / `.bat` files must go through cmd.exe /c."""
    if platform.system() == "Windows" and binpath.lower().endswith((".cmd", ".bat")):
        return ["cmd.exe", "/c", binpath, *args]
    return [binpath, *args]


def probe(binpath: str, timeout: float = 5.0) -> Resolved:
    """Run `<bin> --version` and return a populated Resolved row."""
    r = Resolved(path=binpath, source="probe", candidates_tried=[binpath])
    if not binpath:
        r.error = "empty path"
        return r
    if not Path(binpath).is_file():
        r.error = f"not a file: {binpath}"
        return r
    try:
        argv = wrap_for_platform(binpath, ["--version"])
        out = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        stdout = (out.stdout or "").strip()
        stderr = (out.stderr or "").strip()
        if out.returncode == 0 and stdout:
            r.ok = True
            r.version = stdout.splitlines()[0][:200]
        else:
            r.ok = False
            r.error = (stderr or stdout or f"exit={out.returncode}")[:500]
    except subprocess.TimeoutExpired:
        r.error = f"--version timed out after {timeout}s"
    except Exception as e:
        r.error = f"{e.__class__.__name__}: {e}"
    return r


# ---------------------------------------------------------------------------
# DB-backed override
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_override() -> str | None:
    """Read the user-set claude_bin from the `settings` table."""
    # Local import to avoid circular import at module load.
    from ..db import get_conn
    row = get_conn().execute(
        "SELECT value FROM settings WHERE key=?", (DB_KEY,),
    ).fetchone()
    return (row["value"] if row else None) or None


def set_override(path: str | None, updated_by: str | None = None) -> None:
    """Persist the user-set claude_bin (or clear it if path is empty/None)."""
    from ..db import get_conn
    conn = get_conn()
    if not path:
        conn.execute("DELETE FROM settings WHERE key=?", (DB_KEY,))
        return
    conn.execute(
        """INSERT INTO settings(key, value, updated_at, updated_by)
           VALUES (?,?,?,?)
           ON CONFLICT(key) DO UPDATE SET
             value=excluded.value,
             updated_at=excluded.updated_at,
             updated_by=excluded.updated_by""",
        (DB_KEY, path, _now_iso(), updated_by),
    )


def resolve_current() -> Resolved:
    """Top-level helper: resolve using the DB override if any, else fall back."""
    return resolve(db_override=get_override())
