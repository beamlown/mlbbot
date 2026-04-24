"""Parsers for BOT_BRIDGE artifacts.

Keep permissive: real-world files have schema drift (optional fields missing,
extra fields present, occasional empty files). Parsers skip malformed files and
return `None` instead of raising so the importer can log + continue.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Artifact kind classification by filename
# ---------------------------------------------------------------------------

_KIND_RULES = [
    (re.compile(r"^HANDOFF_.*\.md$",            re.I), "HANDOFF"),
    (re.compile(r"^TASK_.*\.json$",             re.I), "TASK"),
    (re.compile(r"^RESULT_.*\.json$",           re.I), "RESULT"),
    (re.compile(r"^PROVISIONAL_REVIEW_.*\.md$", re.I), "PROVISIONAL_REVIEW"),
    (re.compile(r"^APPROVED_.*\.md$",           re.I), "APPROVED"),
    (re.compile(r"^REVIEW_.*\.md$",             re.I), "REVIEW"),
    (re.compile(r"^CLAUDE_TASK_BOARD\.md$",     re.I), "BOARD"),
    (re.compile(r"^CLAUDE_STATUS\.md$",         re.I), "STATUS"),
    (re.compile(r"^CLAUDE_SOUL\.md$",           re.I), "CONTEXT"),
    (re.compile(r"^.*_SPEC(_\d+)?\.md$",        re.I), "SPEC"),
    (re.compile(r"^.*_AUDIT(_\d+)?.*\.md$",     re.I), "AUDIT"),
]


def classify(filename: str) -> str:
    for rx, kind in _KIND_RULES:
        if rx.match(filename):
            return kind
    if filename.lower().endswith(".md"):
        return "NOTE"
    if filename.lower().endswith(".json"):
        return "JSON"
    return "OTHER"


# The task_id embedded in HANDOFF_XYZ_001.md or RESULT_XYZ_001.json etc.
_ID_FROM_NAME = re.compile(
    r"^(?:HANDOFF|TASK|RESULT|REVIEW|APPROVED|PROVISIONAL_REVIEW)_"
    r"(?P<id>[A-Z0-9_]+?)(?:\.md|\.json)$",
    re.I,
)


def task_id_from_filename(filename: str) -> str | None:
    m = _ID_FROM_NAME.match(filename)
    if not m:
        return None
    return m.group("id").upper()


# ---------------------------------------------------------------------------
# Writer-attribution header (2026-04-18)
#
# Every new artifact file should begin with an HTML comment encoding who
# wrote it, which task/patch it belongs to, and the attempt number:
#
#   <!-- writer: worker, task_id: FOO_001, patch_id: pending, written_at: 2026-04-18T06:12:00Z, attempt: 1 -->
#
# The header is the ground truth the importer uses to route writes to the
# right folder and detect misplacements. Legacy files without this header
# are still accepted (so we don't quarantine everything existing); the
# enforcement is only for files dropped into writer-owned folders.
# ---------------------------------------------------------------------------

_WRITER_HEADER_RE = re.compile(
    r"^\s*<!--\s*"
    r"writer:\s*(?P<writer>[A-Za-z_][A-Za-z0-9_]*)\s*,\s*"
    r"task_id:\s*(?P<task_id>[A-Za-z0-9_-]+)\s*,\s*"
    r"patch_id:\s*(?P<patch_id>[A-Za-z0-9_-]+)\s*,\s*"
    r"written_at:\s*(?P<written_at>[0-9T:+\-Zz.]+)\s*,\s*"
    r"attempt:\s*(?P<attempt>\d+)\s*"
    r"-->\s*$",
    re.MULTILINE,
)

# Folder basename → set of legal writer values. Folders not listed here
# are un-policed (e.g. 04_DRAFTS is operator scratch; 08_SHARED_CONTEXT
# is legacy-mixed).
EXPECTED_WRITER_BY_FOLDER: dict[str, frozenset[str]] = {
    "05_INBOX_FROM_MANAGER": frozenset({"manager", "control_plane", "operator"}),
    "06_OUTBOX_FROM_WORKER": frozenset({"worker"}),
    "07_REVIEWS":            frozenset({"reviewer"}),
    "08_PATCHES":            frozenset({"auditor", "control_plane", "operator"}),
    "10_ARCHIVE":            frozenset({"control_plane"}),
    "99_QUARANTINE":         frozenset({"control_plane"}),
}

# Folders where a missing writer header is tolerated (legacy data lives here).
WRITER_HEADER_LENIENT_FOLDERS: frozenset[str] = frozenset({
    "08_SHARED_CONTEXT",
    "04_DRAFTS",
    "01_RULES",
    "02_PROMPTS",
    "03_TEMPLATES",
    "00_START_HERE",
})


def parse_writer_header(text: str) -> dict | None:
    """Extract the writer-attribution header from the first 4KB of text.

    Returns a dict with keys writer / task_id / patch_id / written_at /
    attempt (attempt as int) on success, or None if no valid header.
    """
    if not text:
        return None
    head = text[:4096]
    m = _WRITER_HEADER_RE.search(head)
    if not m:
        return None
    try:
        attempt = int(m.group("attempt"))
    except (TypeError, ValueError):
        attempt = 1
    return {
        "writer": m.group("writer").lower(),
        "task_id": m.group("task_id").upper(),
        "patch_id": m.group("patch_id"),
        "written_at": m.group("written_at"),
        "attempt": max(1, attempt),
    }


def validate_writer(folder_basename: str, text: str) -> tuple[bool, str]:
    """Verify the writer header matches the folder's writer contract.

    Returns (ok, reason). `ok=True` means either:
      (a) the folder is lenient and tolerates missing headers, or
      (b) the header exists AND its writer is in the folder's allowed set.

    `ok=False` returns a short `reason` string suitable for the
    `quarantined_artifacts.reason` column.
    """
    folder = folder_basename
    allowed = EXPECTED_WRITER_BY_FOLDER.get(folder)
    header = parse_writer_header(text)
    if allowed is None:
        # Un-policed folder → accept either way.
        return True, ""
    if header is None:
        if folder in WRITER_HEADER_LENIENT_FOLDERS:
            return True, ""
        return False, f"missing writer-attribution header in {folder}"
    if header["writer"] not in allowed:
        return False, (
            f"writer={header['writer']!r} not allowed in {folder} "
            f"(expected one of {sorted(allowed)})"
        )
    return True, ""


# ---------------------------------------------------------------------------
# TASK_*.json
# ---------------------------------------------------------------------------

@dataclass
class ParsedTask:
    task_id: str
    title: str
    type: str
    priority: str
    status: str
    issued: str | None
    subsystem: str | None
    allowed_files: list[str]
    forbidden_files: list[str]
    acceptance: str | None
    brief_path: str | None
    result_path: str | None
    review_path: str | None
    evidence: str | None
    raw: dict


_CANONICAL_STATUS = {"PENDING", "QUEUED", "ACTIVE", "BLOCKED", "DONE",
                     "CHANGES_REQUESTED", "ARCHIVED"}
_CANONICAL_PRIORITY = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}


def _normalize_status(raw) -> str:
    """Map free-form status strings in TASK_*.json to one canonical lane.

    Real data contains long phrases like
    'QUEUED — BLOCKED UNTIL SESSION_EXPOSURE_CAP_001 CLOSES'
    or 'HOLD_PENDING_EXECUTION_TRUTH'. Extract the leading token and coerce.
    """
    if raw is None:
        return "PENDING"
    s = str(raw).strip().upper()
    # Take the first word-like chunk before whitespace / dash / em-dash.
    head = re.split(r"[\s\-\u2014/:]", s, maxsplit=1)[0]
    if head in _CANONICAL_STATUS:
        return head
    synonyms = {
        "OPEN": "QUEUED",
        "NEW": "PENDING",
        "PROPOSED": "PENDING",
        "IN_PROGRESS": "ACTIVE",
        "INPROGRESS": "ACTIVE",
        "WIP": "ACTIVE",
        "HOLD": "BLOCKED",
        "HOLD_PENDING_EXECUTION_TRUTH": "BLOCKED",
        "DEFERRED": "BLOCKED",
        "WAITING": "BLOCKED",
        "PROVISIONAL": "ACTIVE",
        "PROVISIONAL_ACTIVE_PENDING_CLAUDE": "ACTIVE",
        "BACKLOG": "QUEUED",
        "SUPERSEDED": "ARCHIVED",
        "CANCELLED": "ARCHIVED",
        "CANCELED": "ARCHIVED",
        "CLOSED": "DONE",
        "COMPLETE": "DONE",
        "COMPLETED": "DONE",
        "APPROVED": "DONE",
        "PASS": "DONE",
        "FAIL": "CHANGES_REQUESTED",
        "CHANGES": "CHANGES_REQUESTED",
    }
    # Match full phrase first, then head word.
    if s in synonyms:
        return synonyms[s]
    if head in synonyms:
        return synonyms[head]
    return "PENDING"


def _normalize_priority(raw) -> str:
    if raw is None:
        return "MEDIUM"
    s = str(raw).strip().upper()
    return s if s in _CANONICAL_PRIORITY else "MEDIUM"


def parse_task_json(path: Path) -> ParsedTask | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict) or "task_id" not in data:
        return None

    def _strlist(v) -> list[str]:
        if isinstance(v, list):
            return [str(x) for x in v]
        if isinstance(v, str):
            return [v]
        return []

    def _acceptance(v) -> str | None:
        if v is None:
            return None
        if isinstance(v, list):
            return "\n".join(f"- {x}" for x in v)
        if isinstance(v, dict):
            return json.dumps(v, indent=2)
        return str(v)

    return ParsedTask(
        task_id=str(data["task_id"]).upper(),
        title=str(data.get("title") or data.get("summary") or data["task_id"]),
        type=str(data.get("type") or "unspecified"),
        priority=_normalize_priority(data.get("priority")),
        status=_normalize_status(data.get("status")),
        issued=data.get("issued"),
        subsystem=data.get("subsystem"),
        allowed_files=_strlist(data.get("allowed_files")),
        forbidden_files=_strlist(data.get("forbidden_files")),
        acceptance=_acceptance(data.get("acceptance")
                               or data.get("acceptance_criteria")
                               or data.get("deliverables")),
        brief_path=data.get("brief_path"),
        result_path=data.get("result_path"),
        review_path=data.get("review_path"),
        evidence=data.get("evidence"),
        raw=data,
    )


# ---------------------------------------------------------------------------
# RESULT_*.json
# ---------------------------------------------------------------------------

@dataclass
class ParsedResult:
    task_id: str
    status: str
    summary: str | None
    files_changed: list[str]
    raw: dict


def parse_result_json(path: Path) -> ParsedResult | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    tid = data.get("task_id") or task_id_from_filename(path.name)
    if not tid:
        return None

    files = data.get("files_changed") or data.get("modified_files") or []
    if not isinstance(files, list):
        files = [str(files)]

    summary = (
        data.get("summary")
        or data.get("final_outcome")
        or data.get("result_summary")
    )
    return ParsedResult(
        task_id=str(tid).upper(),
        status=str(data.get("status") or "DONE").upper(),
        summary=summary if isinstance(summary, str) else None,
        files_changed=[str(f) for f in files],
        raw=data,
    )


# ---------------------------------------------------------------------------
# REVIEW_*.md  / APPROVED_*.md / PROVISIONAL_REVIEW_*.md
# ---------------------------------------------------------------------------

_DECISION_RX = re.compile(
    r"^\s*(?:Decision|Verdict|Outcome)\s*[:\-]\s*"
    r"(APPROVED|CHANGES[_\s]REQUESTED|FAIL|PROVISIONAL(?:[_\s]PASS)?|PARTIAL[_\s]PASS|PROVISIONAL[_\s]REVIEW)\b",
    re.I | re.M,
)


@dataclass
class ParsedReview:
    task_id: str
    decision: str
    summary: str | None


def parse_review_md(path: Path) -> ParsedReview | None:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    tid = task_id_from_filename(path.name)
    if not tid:
        return None
    m = _DECISION_RX.search(text)
    raw = (m.group(1) if m else "").upper().replace(" ", "_")
    # Normalize known synonyms
    if raw.startswith("PROVISIONAL"):
        decision = "PROVISIONAL"
    elif raw.startswith("CHANGES"):
        decision = "CHANGES_REQUESTED"
    elif raw.startswith("PARTIAL"):
        decision = "PROVISIONAL"
    elif raw in ("APPROVED", "FAIL"):
        decision = raw
    else:
        # Fallback: derive from filename prefix
        up = path.name.upper()
        if up.startswith("APPROVED_"):
            decision = "APPROVED"
        elif up.startswith("PROVISIONAL_REVIEW_"):
            decision = "PROVISIONAL"
        else:
            decision = "UNKNOWN"

    # First non-empty line after the decision or the first header-level prose.
    summary = None
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("#") and "Decision" not in s:
            summary = s[:280]
            break
    return ParsedReview(task_id=tid, decision=decision, summary=summary)


# ---------------------------------------------------------------------------
# HANDOFF_*.md — we keep it as raw markdown; extract title + brief summary
# ---------------------------------------------------------------------------

@dataclass
class ParsedHandoff:
    task_id: str
    title: str
    body: str


def parse_handoff_md(path: Path) -> ParsedHandoff | None:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    tid = task_id_from_filename(path.name)
    if not tid:
        return None
    title = tid
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            title = s.lstrip("#").strip() or tid
            break
    return ParsedHandoff(task_id=tid, title=title, body=text)


# ---------------------------------------------------------------------------
# CLAUDE_TASK_BOARD.md — parse the markdown pipe tables into per-lane rows
# ---------------------------------------------------------------------------

_LANE_HEADERS = {
    "ACTIVE":   re.compile(r"^##\s*ACTIVE\b",      re.I | re.M),
    "QUEUED":   re.compile(r"^##\s*QUEUED\b",      re.I | re.M),
    "BACKLOG":  re.compile(r"^##\s*BACKLOG\b",     re.I | re.M),
    "BLOCKED":  re.compile(r"^##\s*BLOCKED\b",     re.I | re.M),
    "DONE":     re.compile(r"^##\s*DONE\b",        re.I | re.M),
}


@dataclass
class ParsedBoardRow:
    lane: str
    task_id: str
    title: str
    priority: str | None
    subsystem: str | None
    allowed_files: str | None
    notes: str | None


def parse_task_board_md(path: Path) -> list[ParsedBoardRow]:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return []
    rows: list[ParsedBoardRow] = []

    # Split by ## headers to isolate per-lane sections.
    sections: list[tuple[str, str]] = []
    lines = text.splitlines()
    current_lane: str | None = None
    buf: list[str] = []
    for line in lines:
        m = re.match(r"^##\s+([A-Z_/ ]+)", line)
        if m:
            if current_lane and buf:
                sections.append((current_lane, "\n".join(buf)))
            head = m.group(1).strip().upper().split()[0]
            # Only track the lanes we care about
            current_lane = head if head in _LANE_HEADERS else None
            buf = []
        else:
            if current_lane:
                buf.append(line)
    if current_lane and buf:
        sections.append((current_lane, "\n".join(buf)))

    for lane, section in sections:
        for row in _parse_pipe_table(section):
            tid = row.get("task_id")
            if not tid:
                continue
            rows.append(ParsedBoardRow(
                lane=lane,
                task_id=tid.upper(),
                title=row.get("title") or tid,
                priority=(row.get("priority") or "").upper() or None,
                subsystem=row.get("subsystem") or row.get("track"),
                allowed_files=row.get("allowed_files"),
                notes=row.get("notes") or row.get("outcome") or row.get("reason"),
            ))
    return rows


def _parse_pipe_table(section: str) -> list[dict[str, str]]:
    """Parse a GFM pipe table inside a markdown section; ignore prose lines."""
    lines = [ln for ln in section.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 2:
        return []
    # Header row
    headers = [c.strip().lower() for c in _split_pipe(lines[0])]
    out: list[dict[str, str]] = []
    for ln in lines[2:]:  # skip separator row
        cells = _split_pipe(ln)
        if len(cells) < 2:
            continue
        cells = (cells + [""] * len(headers))[: len(headers)]
        d = dict(zip(headers, [c.strip() for c in cells]))
        # Strip trailing asterisks/bold decoration from task_id cell
        if "task_id" in d:
            d["task_id"] = re.sub(r"[`*]", "", d["task_id"]).strip()
        out.append(d)
    return out


def _split_pipe(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c for c in s.split("|")]
