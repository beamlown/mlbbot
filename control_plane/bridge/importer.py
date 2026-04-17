"""BOT_BRIDGE → control plane DB importer.

Scans all four bridge subfolders and upserts `artifacts` + `tasks` +
`task_artifacts` rows. Idempotent; safe to call on every app start. Does NOT
write to the filesystem.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..config import SETTINGS
from ..db import get_conn, tx
from .parsers import (
    classify,
    parse_handoff_md,
    parse_result_json,
    parse_review_md,
    parse_task_board_md,
    parse_task_json,
    task_id_from_filename,
)


SUBFOLDERS = (
    "05_INBOX_FROM_MANAGER",
    "06_OUTBOX_FROM_WORKER",
    "07_REVIEWS",
    "08_SHARED_CONTEXT",
)


@dataclass
class ImportReport:
    tasks_seen: int = 0
    tasks_new: int = 0
    tasks_updated: int = 0
    artifacts_seen: int = 0
    artifacts_new: int = 0
    errors: list[str] | None = None
    duration_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "tasks_seen": self.tasks_seen,
            "tasks_new": self.tasks_new,
            "tasks_updated": self.tasks_updated,
            "artifacts_seen": self.artifacts_seen,
            "artifacts_new": self.artifacts_new,
            "errors": self.errors or [],
            "duration_ms": self.duration_ms,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _repo_rel(p: Path) -> str:
    try:
        return str(p.relative_to(SETTINGS.repo_root)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def import_bot_bridge() -> ImportReport:
    """Walk BOT_BRIDGE/ and sync into the DB. Returns an `ImportReport`."""
    report = ImportReport(errors=[])
    t0 = datetime.now(timezone.utc)
    conn = get_conn()

    # ------------------------------------------------------------------
    # 1. Walk and upsert artifacts
    # ------------------------------------------------------------------
    for sub in SUBFOLDERS:
        folder = SETTINGS.bridge_root / sub
        if not folder.is_dir():
            report.errors.append(f"missing folder: {folder}")
            continue
        for fp in sorted(folder.iterdir()):
            if not fp.is_file():
                continue
            try:
                _upsert_artifact(fp, report)
            except Exception as e:
                report.errors.append(f"artifact {fp.name}: {e!r}")

    # ------------------------------------------------------------------
    # 2. Upsert tasks from every TASK_*.json we just recorded
    # ------------------------------------------------------------------
    #    TASK_*.json can live in either 05_INBOX_FROM_MANAGER or
    #    08_SHARED_CONTEXT; iterate both.
    task_paths: list[Path] = []
    for sub in ("05_INBOX_FROM_MANAGER", "08_SHARED_CONTEXT"):
        folder = SETTINGS.bridge_root / sub
        if folder.is_dir():
            task_paths.extend(sorted(folder.glob("TASK_*.json")))

    # Dedupe by task_id — if the same task_id appears in both places, the
    # shared-context copy wins (that's where the canonical snapshot lives
    # after a DONE task, per the repo convention).
    seen: dict[str, Path] = {}
    for p in task_paths:
        tid = task_id_from_filename(p.name)
        if not tid:
            continue
        # Prefer the most-recently-mtime copy (usually 08_SHARED_CONTEXT).
        if tid not in seen or p.stat().st_mtime > seen[tid].stat().st_mtime:
            seen[tid] = p

    for tid, p in seen.items():
        try:
            _upsert_task_from_json(p, report)
        except Exception as e:
            report.errors.append(f"task {p.name}: {e!r}")

    # ------------------------------------------------------------------
    # 3. Reconcile against CLAUDE_TASK_BOARD.md — creates BACKLOG / BLOCKED
    #    entries that don't have a TASK_*.json yet, and updates status for
    #    tasks whose markdown status differs (markdown is authoritative for
    #    lane placement of existing tasks in Phase 1 since we don't yet
    #    regenerate the board ourselves).
    # ------------------------------------------------------------------
    board_md = SETTINGS.bridge_root / "08_SHARED_CONTEXT" / "CLAUDE_TASK_BOARD.md"
    if board_md.exists():
        try:
            rows = parse_task_board_md(board_md)
            _reconcile_board_rows(rows, report)
        except Exception as e:
            report.errors.append(f"board.md: {e!r}")

    # ------------------------------------------------------------------
    # 4. Link artifacts to tasks (HANDOFF, RESULT, REVIEW)
    # ------------------------------------------------------------------
    try:
        _link_artifacts_to_tasks()
    except Exception as e:
        report.errors.append(f"link: {e!r}")

    # ------------------------------------------------------------------
    # 5. Stamp import_log
    # ------------------------------------------------------------------
    t1 = datetime.now(timezone.utc)
    report.duration_ms = int((t1 - t0).total_seconds() * 1000)
    conn.execute(
        """INSERT INTO import_log
           (started_at, finished_at, tasks_seen, tasks_new, tasks_updated,
            artifacts_seen, artifacts_new, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            t0.strftime("%Y-%m-%dT%H:%M:%SZ"),
            t1.strftime("%Y-%m-%dT%H:%M:%SZ"),
            report.tasks_seen, report.tasks_new, report.tasks_updated,
            report.artifacts_seen, report.artifacts_new,
            json.dumps({"errors": (report.errors or [])[:20]}),
        ),
    )
    return report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upsert_artifact(fp: Path, report: ImportReport) -> None:
    report.artifacts_seen += 1
    rel = _repo_rel(fp)
    stat = fp.stat()
    size = stat.st_size
    mtime = int(stat.st_mtime)
    try:
        raw = fp.read_bytes()
    except Exception:
        return
    sha = _sha256(raw)
    # Best-effort text decode. Non-UTF-8 gets stored as None.
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = None

    kind = classify(fp.name)
    tid = task_id_from_filename(fp.name)

    # Build a short summary for browsing.
    title = fp.name
    summary = None
    if kind == "HANDOFF" and text:
        h = parse_handoff_md(fp)
        if h:
            title = h.title
    elif kind == "TASK" and text:
        t = parse_task_json(fp)
        if t:
            title = t.title
            summary = f"priority={t.priority} status={t.status}"
    elif kind == "RESULT" and text:
        r = parse_result_json(fp)
        if r:
            title = f"Result for {r.task_id}"
            summary = r.summary
    elif kind in ("REVIEW", "APPROVED", "PROVISIONAL_REVIEW") and text:
        v = parse_review_md(fp)
        if v:
            title = f"{v.decision} — {v.task_id}"
            summary = v.summary

    conn = get_conn()
    row = conn.execute("SELECT artifact_id, sha256 FROM artifacts WHERE path=?", (rel,)).fetchone()
    if row is None:
        aid = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO artifacts
               (artifact_id, kind, path, title, summary, task_ref, mtime,
                size_bytes, sha256, content, discovered_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (aid, kind, rel, title, summary, tid, mtime, size, sha, text, _now_iso()),
        )
        report.artifacts_new += 1
    elif row["sha256"] != sha:
        conn.execute(
            """UPDATE artifacts SET kind=?, title=?, summary=?, task_ref=?,
                                    mtime=?, size_bytes=?, sha256=?, content=?
                WHERE artifact_id=?""",
            (kind, title, summary, tid, mtime, size, sha, text, row["artifact_id"]),
        )


def _upsert_task_from_json(path: Path, report: ImportReport) -> None:
    parsed = parse_task_json(path)
    if parsed is None:
        return
    report.tasks_seen += 1
    tid = parsed.task_id
    now = _now_iso()
    raw_bytes = path.read_bytes()
    ext_hash = _sha256(raw_bytes)
    ext_mtime = int(path.stat().st_mtime)

    conn = get_conn()
    row = conn.execute("SELECT task_id FROM tasks WHERE task_id=?", (tid,)).fetchone()
    if row is None:
        conn.execute(
            """INSERT INTO tasks
               (task_id, type, priority, status, issued, subsystem, title,
                evidence, allowed_files, forbidden_files, acceptance,
                brief_path, result_path, review_path, source,
                external_mtime, external_hash, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                tid, parsed.type, parsed.priority, parsed.status, parsed.issued,
                parsed.subsystem, parsed.title, parsed.evidence,
                json.dumps(parsed.allowed_files),
                json.dumps(parsed.forbidden_files),
                parsed.acceptance,
                parsed.brief_path, parsed.result_path, parsed.review_path,
                "import", ext_mtime, ext_hash, now, now,
            ),
        )
        report.tasks_new += 1
    else:
        conn.execute(
            """UPDATE tasks SET
                type=?, priority=?, status=?, issued=?, subsystem=?, title=?,
                evidence=?, allowed_files=?, forbidden_files=?, acceptance=?,
                brief_path=COALESCE(?, brief_path),
                result_path=COALESCE(?, result_path),
                review_path=COALESCE(?, review_path),
                external_mtime=?, external_hash=?, updated_at=?
               WHERE task_id=?""",
            (
                parsed.type, parsed.priority, parsed.status, parsed.issued,
                parsed.subsystem, parsed.title, parsed.evidence,
                json.dumps(parsed.allowed_files),
                json.dumps(parsed.forbidden_files),
                parsed.acceptance,
                parsed.brief_path, parsed.result_path, parsed.review_path,
                ext_mtime, ext_hash, now, tid,
            ),
        )
        report.tasks_updated += 1


def _reconcile_board_rows(rows, report: ImportReport) -> None:
    """
    For each row in CLAUDE_TASK_BOARD.md:
      - if a task exists, set its status to the lane-derived status.
      - if no task exists, create a shell task from the markdown row so the
        board view isn't missing BACKLOG / BLOCKED / DONE-only entries.
    """
    lane_to_status = {
        "ACTIVE":   "ACTIVE",
        "QUEUED":   "QUEUED",
        "BACKLOG":  "QUEUED",
        "BLOCKED":  "BLOCKED",
        "DONE":     "DONE",
    }
    conn = get_conn()
    for i, row in enumerate(rows):
        status = lane_to_status.get(row.lane)
        if not status:
            continue
        existing = conn.execute(
            "SELECT task_id, status, source FROM tasks WHERE task_id=?",
            (row.task_id,),
        ).fetchone()
        now = _now_iso()
        if existing is None:
            # Shell task from markdown only (e.g. DONE rows that don't have a
            # matching TASK_*.json any more).
            conn.execute(
                """INSERT INTO tasks
                   (task_id, type, priority, status, subsystem, title, notes,
                    allowed_files, source, lane_order, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    row.task_id,
                    "imported_from_board",
                    row.priority or "MEDIUM",
                    status,
                    row.subsystem,
                    row.title,
                    row.notes,
                    json.dumps([row.allowed_files] if row.allowed_files else []),
                    "board_md",
                    i,
                    now, now,
                ),
            )
            report.tasks_new += 1
            report.tasks_seen += 1
        else:
            # CLAUDE_TASK_BOARD.md is the authoritative source for LANE
            # placement because old TASK_*.json files often still say
            # "ACTIVE" after they were moved to DONE. Always trust the
            # markdown for status + lane_order; keep JSON priority unless
            # the markdown provided one.
            conn.execute(
                """UPDATE tasks SET status=?,
                                    priority=COALESCE(?, priority),
                                    subsystem=COALESCE(subsystem, ?),
                                    notes=COALESCE(?, notes),
                                    lane_order=?, updated_at=?
                    WHERE task_id=?""",
                (status, row.priority or None, row.subsystem,
                 row.notes, i, now, row.task_id),
            )


def _link_artifacts_to_tasks() -> None:
    conn = get_conn()
    kind_to_relation = {
        "HANDOFF": "brief",
        "TASK": "task_json",
        "RESULT": "result",
        "REVIEW": "review",
        "APPROVED": "review",
        "PROVISIONAL_REVIEW": "review",
    }
    # Fresh links every import to keep the table in sync.
    conn.execute("DELETE FROM task_artifacts")
    rows = conn.execute(
        "SELECT artifact_id, kind, task_ref FROM artifacts WHERE task_ref IS NOT NULL"
    ).fetchall()
    for r in rows:
        rel = kind_to_relation.get(r["kind"])
        if not rel:
            continue
        tid = r["task_ref"]
        exists = conn.execute("SELECT 1 FROM tasks WHERE task_id=?", (tid,)).fetchone()
        if not exists:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO task_artifacts(task_id, artifact_id, relation) VALUES (?,?,?)",
            (tid, r["artifact_id"], rel),
        )
