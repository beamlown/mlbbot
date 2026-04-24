"""Regenerate `CLAUDE_TASK_BOARD.md` — prose-preserving.

The board markdown has operator prose interleaved with pipe tables:
- Prefix (title, "Last updated", "Policy Reminders") before the first
  `## ACTIVE`.
- Each lane section (ACTIVE / QUEUED / BACKLOG / BLOCKED / DONE) has a
  header, optional prose, then a pipe table.
- Free-form sections like "BACKLOG / OVERLAP NOTES", "Conflict Map",
  "System state" appear between and after the lane sections.

Strategy: walk the file line-by-line. For each recognized lane heading,
replace only the first pipe table that follows it; leave everything else
untouched. If a lane heading does not exist yet, append a fresh section.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from ..config import SETTINGS
from ..db import get_conn


# Lanes we actively regenerate. BACKLOG was historically a second QUEUED-like
# lane in the markdown; we fold it into QUEUED in the DB, and leave BACKLOG's
# table empty (prose-only) rather than double-write. Operator can merge if
# they want.
MANAGED_LANES = ("ACTIVE", "QUEUED", "BLOCKED", "DONE")


BOARD_PATH = lambda: SETTINGS.bridge_root / "08_SHARED_CONTEXT" / "CLAUDE_TASK_BOARD.md"  # noqa: E731


# ---------------------------------------------------------------------------
# Table generators per lane
# ---------------------------------------------------------------------------

PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _tasks_in(status: str) -> list[dict]:
    rows = get_conn().execute(
        "SELECT * FROM tasks WHERE status=? ORDER BY lane_order ASC, priority ASC, task_id ASC",
        (status,),
    ).fetchall()
    items = [dict(r) for r in rows]
    # Stable sort by priority then lane_order.
    items.sort(key=lambda t: (PRIORITY_ORDER.get((t.get("priority") or "MEDIUM"), 2),
                              t.get("lane_order", 0) or 0,
                              t["task_id"]))
    return items


def _allowed_files_cell(t: dict) -> str:
    import json
    try:
        v = json.loads(t.get("allowed_files") or "[]")
    except Exception:
        v = []
    if not isinstance(v, list) or not v:
        return ""
    return ", ".join(f"`{x}`" for x in v[:6]) + ("…" if len(v) > 6 else "")


def _escape(s: str | None) -> str:
    if s is None:
        return ""
    return str(s).replace("|", "\\|").replace("\n", " ").strip()


def _table_for_lane(lane: str) -> str:
    tasks = _tasks_in(lane)
    if lane in ("ACTIVE", "QUEUED"):
        header = "| task_id | title | priority | subsystem | allowed_files | notes |"
        sep    = "|---------|-------|----------|-----------|---------------|-------|"
        rows = [
            f"| {_escape(t['task_id'])} "
            f"| {_escape(t.get('title'))} "
            f"| {_escape(t.get('priority'))} "
            f"| {_escape(t.get('subsystem'))} "
            f"| {_allowed_files_cell(t)} "
            f"| {_escape(t.get('notes'))} |"
            for t in tasks
        ]
    elif lane == "BLOCKED":
        header = "| task_id | title | reason | unblocked_by |"
        sep    = "|---------|-------|--------|--------------|"
        rows = [
            f"| {_escape(t['task_id'])} "
            f"| {_escape(t.get('title'))} "
            f"| {_escape(t.get('notes') or t.get('outcome'))} "
            f"| {_escape(t.get('assigned_role') or '')} |"
            for t in tasks
        ]
    elif lane == "DONE":
        header = "| task_id | title | outcome | allowed_files |"
        sep    = "|---------|-------|---------|---------------|"
        rows = [
            f"| {_escape(t['task_id'])} "
            f"| {_escape(t.get('title'))} "
            f"| {_escape(t.get('outcome') or t.get('notes') or '')} "
            f"| {_allowed_files_cell(t)} |"
            for t in tasks
        ]
    else:
        return ""
    if not rows:
        rows = ["| _(none)_ |  |  |  |  |  |"]
    return "\n".join([header, sep, *rows])


# ---------------------------------------------------------------------------
# Surgical file rewriter
# ---------------------------------------------------------------------------

_HEADING_RX = re.compile(r"^##\s+(?P<name>[A-Za-z0-9_/ \-]+)\s*$")
_TABLE_LINE = re.compile(r"^\s*\|")


def _split_sections(lines: list[str]) -> list[tuple[str | None, list[str]]]:
    """Split the markdown into (lane_name | None, block_lines) sections.

    `lane_name` is the uppercased first word of a `##` heading if it is one of
    our managed lanes; else None. Prefix before the first `##` is emitted with
    lane_name=None. Trailing non-managed sections are preserved as-is.
    """
    sections: list[tuple[str | None, list[str]]] = []
    current_name: str | None = None
    current: list[str] = []
    for line in lines:
        m = _HEADING_RX.match(line)
        if m:
            # Flush the previous block.
            sections.append((current_name, current))
            head = m.group("name").strip().split()[0].upper()
            current_name = head if head in MANAGED_LANES else None
            current = [line]
        else:
            current.append(line)
    sections.append((current_name, current))
    return sections


def _replace_table_in_block(block: list[str], new_table: str) -> list[str]:
    """Replace the first pipe-table inside `block` with `new_table`.

    Preserves everything before and after the table (prose + the heading line
    at block[0]). If no table exists, append one after the last non-blank line.
    """
    # Find the table start (first line beginning with '|').
    start_i = None
    for i, line in enumerate(block):
        if _TABLE_LINE.match(line):
            start_i = i
            break
    if start_i is None:
        # Append the table at the end of the section, with a blank line above.
        tail = list(block)
        while tail and tail[-1].strip() == "":
            tail.pop()
        return tail + ["", new_table, ""]

    # Consume contiguous pipe-table lines including the separator.
    end_i = start_i
    while end_i < len(block) and (_TABLE_LINE.match(block[end_i]) or block[end_i].strip() == ""):
        # Stop the block if we see a blank line followed by non-pipe prose.
        if block[end_i].strip() == "":
            # Peek forward — if the next non-blank is still pipe, continue.
            j = end_i + 1
            while j < len(block) and block[j].strip() == "":
                j += 1
            if j < len(block) and _TABLE_LINE.match(block[j]):
                end_i = j
                continue
            break
        end_i += 1
    return block[:start_i] + [new_table] + block[end_i:]


def regenerate_board_md(*, dry_run: bool = False) -> dict:
    """Rewrite the lane pipe-tables in `CLAUDE_TASK_BOARD.md` in place.

    Prose, prefix, and non-managed sections are preserved verbatim. Returns
    a dict with the resulting path + hash for UI surfacing.
    """
    path = BOARD_PATH()
    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        text = _fresh_board_skeleton()

    lines = text.splitlines()
    sections = _split_sections(lines)

    # For each managed lane that exists in the file, swap its table. Collect
    # names we found so we can append any missing lanes at the end in a
    # predictable order.
    seen: set[str] = set()
    rebuilt: list[list[str]] = []
    for name, block in sections:
        if name in MANAGED_LANES:
            seen.add(name)
            new_table = _table_for_lane(name)
            rebuilt.append(_replace_table_in_block(block, new_table))
        else:
            rebuilt.append(block)

    # Append missing managed lanes (rare — only when editing a board that
    # never had, say, a BLOCKED section).
    for lane in MANAGED_LANES:
        if lane not in seen:
            rebuilt.append([f"## {lane}", "", _table_for_lane(lane), ""])

    flat = [ln for block in rebuilt for ln in block]
    # Collapse multiple blank lines to at most 1 within the file.
    out = _collapse_blank_runs("\n".join(flat))
    out = _ensure_last_updated_note(out)

    sha = hashlib.sha256(out.encode("utf-8")).hexdigest()
    if dry_run:
        return {"ok": True, "path": str(path), "sha256": sha, "dry_run": True, "content": out}

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(out, encoding="utf-8")
    return {"ok": True, "path": str(path), "sha256": sha, "bytes": len(out.encode("utf-8"))}


def _collapse_blank_runs(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text.rstrip() + "\n")


def _ensure_last_updated_note(text: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    note = f"<!-- regenerated by control_plane at {ts} -->"
    if "<!-- regenerated by control_plane" in text:
        return re.sub(r"<!-- regenerated by control_plane[^>]*-->", note, text)
    # Insert after the first heading line.
    lines = text.splitlines()
    out: list[str] = []
    inserted = False
    for i, line in enumerate(lines):
        out.append(line)
        if not inserted and line.startswith("#") and i == 0:
            out.append(note)
            inserted = True
    if not inserted:
        out.insert(0, note)
    return "\n".join(out) + ("\n" if not text.endswith("\n") else "")


def _fresh_board_skeleton() -> str:
    return (
        "# CLAUDE_TASK_BOARD.md — Manager Task Board\n"
        "## Last updated: (auto)\n\n"
        "---\n\n"
        "## Policy Reminders\n"
        "- Max 3 ACTIVE tasks at once\n"
        "- No two ACTIVE tasks may touch the same file\n"
        "- New conflicting tasks → QUEUED, not ACTIVE\n\n"
        "---\n\n"
        "## ACTIVE\n\n\n"
        "## QUEUED\n\n\n"
        "## BLOCKED\n\n\n"
        "## DONE\n\n"
    )


# ---------------------------------------------------------------------------
# Wrapper used by routes
# ---------------------------------------------------------------------------

def regenerate_if_board_exists() -> dict:
    """Convenience for routes: regenerate unconditionally and return result."""
    return regenerate_board_md()
