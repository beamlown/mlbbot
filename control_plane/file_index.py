"""Workspace file index — the prompt builder's lookup of canonical paths.

Agents kept searching Desktop\\sports_bot_v2, Desktop\\mlbbot\\sports_bot_v2,
and Desktop\\BOT_BRIDGE interchangeably because the task's `allowed_files`
sometimes carried absolute paths, sometimes bare filenames, and the old
prompt layout block described a mlbbot-centric tree that didn't match
the real multi-repo workspace.

This module walks the control-plane-hosting repo (mlbbot) plus its
sibling project roots (sports_bot_v2, mlb_model, march_madness_bot),
indexes every text file it finds, and exposes a `resolve()` helper the
prompt builder uses to map a bare filename to its canonical absolute
path — or to list all candidates if the name is ambiguous.

Scan is cheap (~1s on a typical workspace) and runs at server startup,
with a `reindex()` entry point for manual re-runs after big changes.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import SETTINGS
from .db import get_conn


log = logging.getLogger(__name__)


# File extensions we index. Anything else is skipped outright so the
# table doesn't balloon with build artifacts or binary blobs.
_INDEXED_EXTS = {
    ".py", ".md", ".json", ".yaml", ".yml", ".toml", ".txt",
    ".html", ".css", ".js", ".ts", ".tsx", ".jsx",
    ".sql", ".sh", ".bat", ".ps1",
    ".ini", ".cfg", ".env",
}

# Directory names to skip entirely during the walk. These are noise the
# agent never needs to look inside.
_SKIP_DIRS = {
    ".git", ".hg", ".svn",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "node_modules", ".venv", "venv", "env",
    ".idea", ".vscode",
    "dist", "build", ".next", ".turbo",
    "site-packages",
}

# Files larger than this are skipped — they're almost certainly not
# something an agent should open inline.
_MAX_FILE_BYTES = 1_000_000


def _project_roots() -> list[tuple[str, Path]]:
    """Return (label, path) for each project root we want indexed.

    The control plane's repo is always included. Siblings are included
    if the directory exists — we never index paths we can't see.
    """
    repo = SETTINGS.repo_root
    parent = repo.parent
    roots: list[tuple[str, Path]] = [(repo.name, repo)]
    for sibling in ("sports_bot_v2", "mlb_model", "march_madness_bot"):
        p = parent / sibling
        if p.is_dir():
            roots.append((sibling, p))
    return roots


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def reindex() -> dict:
    """Walk every project root and refresh the known_files table.

    Returns a small report dict for the /system UI + startup log. This
    operation is idempotent — subsequent calls replace the table in one
    pass so deletions on disk disappear from the index.
    """
    t0 = time.time()
    conn = get_conn()
    conn.execute("DELETE FROM known_files")
    now = _now_iso()
    total = 0
    by_root: dict[str, int] = {}

    for label, root in _project_roots():
        count = 0
        for dirpath, dirnames, filenames in os.walk(root):
            # Prune skip dirs in-place so os.walk doesn't descend.
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in _INDEXED_EXTS:
                    continue
                full = Path(dirpath) / fn
                try:
                    st = full.stat()
                except OSError:
                    continue
                if st.st_size > _MAX_FILE_BYTES:
                    continue
                conn.execute(
                    """INSERT OR REPLACE INTO known_files
                       (abs_path, basename, root, kind, size_bytes, mtime, indexed_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (str(full), fn, label, ext, st.st_size, int(st.st_mtime), now),
                )
                count += 1
        by_root[label] = count
        total += count

    elapsed = time.time() - t0
    log.info("file_index.reindex: %d files across %d roots in %.2fs",
             total, len(by_root), elapsed)
    return {"total": total, "by_root": by_root, "elapsed_s": round(elapsed, 2)}


def resolve(name: str) -> list[str]:
    """Return absolute paths matching a bare filename or relative path.

    Empty list if unknown. Single-element list if the name is unambiguous.
    Multi-element list if the same basename lives in multiple roots —
    the prompt builder will render all candidates so the agent sees the
    ambiguity and can ask/pick.
    """
    if not name:
        return []
    name = name.strip()
    # Accept a trailing path separator stripped; agents sometimes paste
    # `sports_bot_v2\\bot_core.py` — try suffix match for those.
    basename = os.path.basename(name.replace("\\", "/"))
    rows = get_conn().execute(
        "SELECT abs_path FROM known_files WHERE basename=?", (basename,)
    ).fetchall()
    paths = [r["abs_path"] for r in rows]
    # If the caller provided a partial path (contains a separator), prefer
    # matches whose abs_path ends with the given fragment.
    if "/" in name or "\\" in name:
        frag = name.replace("/", os.sep).replace("\\", os.sep)
        narrowed = [p for p in paths if p.endswith(frag)]
        if narrowed:
            return narrowed
    return paths


def resolve_task_files(paths: list[str]) -> list[dict]:
    """Resolve a task's allowed_files or forbidden_files list.

    Each returned dict is:
      {"given": original_string, "status": "ok"|"missing"|"ambiguous",
       "resolved": [abs_path, ...]}

    - absolute paths that exist on disk → ok, single-element resolved
    - absolute paths that don't exist  → missing, empty resolved
    - bare filenames / relative paths  → resolve() lookup (may be ok or
      ambiguous depending on how many roots carry that basename)
    """
    out: list[dict] = []
    for p in paths or []:
        if not isinstance(p, str) or not p.strip():
            continue
        raw = p.strip()
        norm = raw.replace("/", os.sep).replace("\\", os.sep)
        # Absolute on Windows (X:\...) or POSIX (/...)?
        is_abs = os.path.isabs(norm)
        if is_abs:
            if os.path.exists(norm):
                out.append({"given": raw, "status": "ok", "resolved": [norm]})
            else:
                # Last-ditch: maybe the basename matches an indexed file
                # and the operator just wrote the wrong root. Offer that.
                candidates = resolve(os.path.basename(norm))
                if len(candidates) == 1:
                    out.append({"given": raw, "status": "ok",
                                "resolved": candidates,
                                "note": "path as given was missing; resolved via index"})
                elif candidates:
                    out.append({"given": raw, "status": "ambiguous",
                                "resolved": candidates})
                else:
                    out.append({"given": raw, "status": "missing", "resolved": []})
        else:
            candidates = resolve(raw)
            if len(candidates) == 1:
                out.append({"given": raw, "status": "ok", "resolved": candidates})
            elif candidates:
                out.append({"given": raw, "status": "ambiguous",
                            "resolved": candidates})
            else:
                out.append({"given": raw, "status": "missing", "resolved": []})
    return out
