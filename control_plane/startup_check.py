"""Anti-drift guardrails run at app startup and cached for /system UI.

Five checks; any FAIL blocks boot unless CONTROL_PLANE_FORCE_START=1:

1. legacy_cutoff    — the old Desktop\\BOT_BRIDGE\\ tree must be frozen
2. orphan_sources   — no mlbbot\\sports_bot_v2\\ or ORPHAN_ARCHIVE_* tree
                      with a live bot.pid
3. bridge_structure — canonical bridge root has the required subfolders
4. single_bridge    — bridge_root points at the canonical mlbbot path
5. role_configs     — .claude-roles/*/CLAUDE.md don't reference legacy paths
                      (WARN, not FAIL — surfaces in banner)
"""
from __future__ import annotations

import glob
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .config import SETTINGS


REQUIRED_BRIDGE_SUBFOLDERS: tuple[str, ...] = (
    "00_START_HERE",
    "01_RULES",
    "04_DRAFTS",
    "05_INBOX_FROM_MANAGER",
    "06_OUTBOX_FROM_WORKER",
    "07_REVIEWS",
    "08_PATCHES",
    "08_SHARED_CONTEXT",
    "10_ARCHIVE",
    "99_QUARANTINE",
)

CANONICAL_BRIDGE_HINT = r"mlbbot\BOT_BRIDGE"


@dataclass
class GuardrailResult:
    name: str
    ok: bool
    severity: str  # "fail" | "warn" | "info"
    detail: str
    violating_paths: list[str] = field(default_factory=list)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid
            )
            if not h:
                return False
            exit_code = ctypes.c_ulong()
            ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(exit_code))
            ctypes.windll.kernel32.CloseHandle(h)
            # STILL_ACTIVE = 259
            return bool(ok) and exit_code.value == 259
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


def check_legacy_cutoff() -> GuardrailResult:
    """Legacy Desktop\\BOT_BRIDGE\\ must be frozen after the cutoff."""
    root = SETTINGS.legacy_bridge_root
    cutoff = SETTINGS.legacy_cutoff_ts
    if not root.exists():
        return GuardrailResult(
            name="legacy_cutoff",
            ok=True,
            severity="info",
            detail=f"legacy tree {root} absent; nothing to freeze",
        )
    violators: list[str] = []
    try:
        for p in root.rglob("*"):
            try:
                if not p.is_file():
                    continue
                if p.stat().st_mtime > cutoff:
                    violators.append(str(p))
                    if len(violators) > 25:
                        violators.append(f"… (more than 25 violations — truncated)")
                        break
            except OSError:
                continue
    except OSError as e:
        return GuardrailResult(
            name="legacy_cutoff",
            ok=False,
            severity="fail",
            detail=f"could not walk legacy tree: {e}",
        )
    if violators:
        return GuardrailResult(
            name="legacy_cutoff",
            ok=False,
            severity="fail",
            detail=(
                f"{len(violators)} file(s) under legacy {root} modified after "
                f"{_iso(cutoff)}; that tree is frozen"
            ),
            violating_paths=violators,
        )
    return GuardrailResult(
        name="legacy_cutoff",
        ok=True,
        severity="info",
        detail=f"legacy {root} clean since {_iso(cutoff)}",
    )


def check_orphan_sources() -> GuardrailResult:
    """No orphan source tree may have a live bot.pid."""
    alive: list[str] = []
    for pattern in SETTINGS.orphan_source_globs:
        for match in glob.glob(pattern):
            pid_file = Path(match) / "runtime" / "bot.pid"
            if not pid_file.exists():
                continue
            try:
                pid = int(pid_file.read_text().strip())
            except (ValueError, OSError):
                continue
            if _pid_alive(pid):
                alive.append(f"{pid_file} → PID {pid} alive")
    if alive:
        return GuardrailResult(
            name="orphan_sources",
            ok=False,
            severity="fail",
            detail=f"{len(alive)} orphan source tree(s) running a live bot",
            violating_paths=alive,
        )
    return GuardrailResult(
        name="orphan_sources",
        ok=True,
        severity="info",
        detail="no orphan source trees running a live bot",
    )


def check_bridge_structure() -> GuardrailResult:
    root = SETTINGS.bridge_root
    if not root.exists():
        return GuardrailResult(
            name="bridge_structure",
            ok=False,
            severity="fail",
            detail=f"canonical BRIDGE_ROOT {root} does not exist",
        )
    missing = [s for s in REQUIRED_BRIDGE_SUBFOLDERS if not (root / s).is_dir()]
    if missing:
        return GuardrailResult(
            name="bridge_structure",
            ok=False,
            severity="fail",
            detail=f"missing required subfolders: {', '.join(missing)}",
            violating_paths=[str(root / m) for m in missing],
        )
    return GuardrailResult(
        name="bridge_structure",
        ok=True,
        severity="info",
        detail=f"canonical BRIDGE_ROOT {root} has all {len(REQUIRED_BRIDGE_SUBFOLDERS)} required subfolders",
    )


def check_single_bridge() -> GuardrailResult:
    """BRIDGE_ROOT must live inside mlbbot\\BOT_BRIDGE (not the legacy path)."""
    root = str(SETTINGS.bridge_root).lower()
    legacy = str(SETTINGS.legacy_bridge_root).lower()
    if root == legacy:
        return GuardrailResult(
            name="single_bridge",
            ok=False,
            severity="fail",
            detail=f"BRIDGE_ROOT points at the legacy path {SETTINGS.bridge_root}; must be mlbbot\\BOT_BRIDGE",
        )
    if CANONICAL_BRIDGE_HINT.lower() not in root:
        return GuardrailResult(
            name="single_bridge",
            ok=False,
            severity="fail",
            detail=f"BRIDGE_ROOT {SETTINGS.bridge_root} is not under the canonical mlbbot\\BOT_BRIDGE path",
        )
    return GuardrailResult(
        name="single_bridge",
        ok=True,
        severity="info",
        detail=f"BRIDGE_ROOT {SETTINGS.bridge_root} is canonical",
    )


_LEGACY_PATH_RE = re.compile(
    r"(?:C:[\\/]+Users[\\/]+johnny[\\/]+Desktop[\\/]+BOT_BRIDGE)"
    r"|(?:C:[\\/]+Users[\\/]+johnny[\\/]+Desktop[\\/]+mlbbot[\\/]+sports_bot_v2(?![\\w])"
    r"(?!\.ORPHAN_ARCHIVE))",
    re.IGNORECASE,
)


def check_role_configs() -> GuardrailResult:
    """Scan .claude-roles/*/CLAUDE.md for references to legacy paths (WARN)."""
    roles_dir = SETTINGS.repo_root / ".claude-roles"
    if not roles_dir.exists():
        return GuardrailResult(
            name="role_configs",
            ok=True,
            severity="info",
            detail=f".claude-roles/ not present at {roles_dir}",
        )
    hits: list[str] = []
    for claude_md in roles_dir.glob("*/CLAUDE.md"):
        try:
            text = claude_md.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _LEGACY_PATH_RE.search(text):
            hits.append(str(claude_md))
    if hits:
        return GuardrailResult(
            name="role_configs",
            ok=False,
            severity="warn",
            detail=f"{len(hits)} role config(s) reference legacy paths; update them",
            violating_paths=hits,
        )
    return GuardrailResult(
        name="role_configs",
        ok=True,
        severity="info",
        detail="role configs clean of legacy path references",
    )


def run_all() -> list[GuardrailResult]:
    return [
        check_legacy_cutoff(),
        check_orphan_sources(),
        check_bridge_structure(),
        check_single_bridge(),
        check_role_configs(),
    ]


def enforce_on_boot() -> list[GuardrailResult]:
    """Run all guardrails; raise RuntimeError on any FAIL unless forced."""
    results = run_all()
    fails = [r for r in results if r.severity == "fail" and not r.ok]
    warns = [r for r in results if r.severity == "warn" and not r.ok]

    for r in results:
        badge = "OK  " if r.ok else ("WARN" if r.severity == "warn" else "FAIL")
        print(f"[startup_check] {badge} {r.name}: {r.detail}", file=sys.stderr)
        for p in r.violating_paths[:5]:
            print(f"[startup_check]      - {p}", file=sys.stderr)

    if fails and not SETTINGS.force_start:
        names = ", ".join(r.name for r in fails)
        raise RuntimeError(
            f"startup guardrails failed: {names} "
            f"(set CONTROL_PLANE_FORCE_START=1 to override)"
        )
    return results


# Module-level cache of last run + timestamp, for the /api/system/guardrails endpoint.
_CACHE: list[GuardrailResult] = []
_CACHE_TS: float = 0.0
_CACHE_TTL_SECONDS: float = 30.0


def cached_results(force: bool = False) -> list[GuardrailResult]:
    global _CACHE, _CACHE_TS
    now = time.time()
    if force or not _CACHE or (now - _CACHE_TS) > _CACHE_TTL_SECONDS:
        _CACHE = run_all()
        _CACHE_TS = now
    return _CACHE


def result_to_dict(r: GuardrailResult) -> dict:
    return {
        "name": r.name,
        "ok": r.ok,
        "severity": r.severity,
        "detail": r.detail,
        "violating_paths": r.violating_paths,
    }
