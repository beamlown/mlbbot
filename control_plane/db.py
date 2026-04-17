"""SQLite persistence layer.

One connection-factory + idempotent DDL. Rows come back as dict-like
`sqlite3.Row`. WAL mode for concurrent reads while a run streams logs.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import SETTINGS


SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
  version    INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
  task_id         TEXT PRIMARY KEY,
  type            TEXT NOT NULL DEFAULT 'unspecified',
  priority        TEXT NOT NULL DEFAULT 'MEDIUM',
  status          TEXT NOT NULL DEFAULT 'PENDING',
  issued          TEXT,
  subsystem       TEXT,
  title           TEXT NOT NULL,
  evidence        TEXT,
  allowed_files   TEXT NOT NULL DEFAULT '[]',
  forbidden_files TEXT NOT NULL DEFAULT '[]',
  acceptance      TEXT,
  notes           TEXT,
  brief_path      TEXT,
  result_path     TEXT,
  review_path     TEXT,
  assigned_role   TEXT,
  lane_order      INTEGER NOT NULL DEFAULT 0,
  outcome         TEXT,
  source          TEXT NOT NULL DEFAULT 'import',
  external_mtime  INTEGER,
  external_hash   TEXT,
  conflict        INTEGER NOT NULL DEFAULT 0,
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_status    ON tasks(status, lane_order);
CREATE INDEX IF NOT EXISTS idx_tasks_subsystem ON tasks(subsystem);
CREATE INDEX IF NOT EXISTS idx_tasks_priority  ON tasks(priority);

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id   TEXT PRIMARY KEY,
  kind          TEXT NOT NULL,
  path          TEXT NOT NULL UNIQUE,
  title         TEXT,
  summary       TEXT,
  task_ref      TEXT,
  mtime         INTEGER NOT NULL,
  size_bytes    INTEGER NOT NULL DEFAULT 0,
  sha256        TEXT NOT NULL,
  content       TEXT,
  discovered_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_artifacts_kind ON artifacts(kind);
CREATE INDEX IF NOT EXISTS idx_artifacts_task ON artifacts(task_ref);

CREATE TABLE IF NOT EXISTS task_artifacts (
  task_id     TEXT NOT NULL,
  artifact_id TEXT NOT NULL,
  relation    TEXT NOT NULL,
  PRIMARY KEY (task_id, artifact_id, relation),
  FOREIGN KEY (task_id)     REFERENCES tasks(task_id)          ON DELETE CASCADE,
  FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id)  ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS runs (
  run_id         TEXT PRIMARY KEY,
  task_id        TEXT,
  role           TEXT NOT NULL,
  adapter        TEXT NOT NULL,
  status         TEXT NOT NULL,
  pid            INTEGER,
  cmdline        TEXT,
  prompt_text    TEXT,
  started_at     TEXT,
  finished_at    TEXT,
  exit_code      INTEGER,
  stdout_path    TEXT,
  stderr_path    TEXT,
  result_summary TEXT,
  created_at     TEXT NOT NULL,
  created_by     TEXT,
  FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_task   ON runs(task_id, created_at DESC);

CREATE TABLE IF NOT EXISTS run_logs (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id  TEXT NOT NULL,
  ts      TEXT NOT NULL,
  stream  TEXT NOT NULL,
  line    TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_run_logs_run ON run_logs(run_id, id);

CREATE TABLE IF NOT EXISTS reviews (
  review_id   TEXT PRIMARY KEY,
  task_id     TEXT NOT NULL,
  run_id      TEXT,
  decision    TEXT NOT NULL,
  reviewer    TEXT NOT NULL,
  summary     TEXT,
  artifact_id TEXT,
  created_at  TEXT NOT NULL,
  FOREIGN KEY (task_id)     REFERENCES tasks(task_id)         ON DELETE CASCADE,
  FOREIGN KEY (run_id)      REFERENCES runs(run_id)           ON DELETE SET NULL,
  FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_reviews_task ON reviews(task_id, created_at DESC);

CREATE TABLE IF NOT EXISTS comments (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  parent_kind TEXT NOT NULL,
  parent_id   TEXT NOT NULL,
  author      TEXT NOT NULL,
  body        TEXT NOT NULL,
  created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_comments_parent ON comments(parent_kind, parent_id, created_at);

CREATE TABLE IF NOT EXISTS settings (
  key        TEXT PRIMARY KEY,
  value      TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT
);

CREATE TABLE IF NOT EXISTS import_log (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  tasks_seen INTEGER DEFAULT 0,
  tasks_new  INTEGER DEFAULT 0,
  tasks_updated INTEGER DEFAULT 0,
  artifacts_seen INTEGER DEFAULT 0,
  artifacts_new  INTEGER DEFAULT 0,
  notes      TEXT
);

CREATE TABLE IF NOT EXISTS agent_profiles (
  profile_id     TEXT PRIMARY KEY,
  display        TEXT NOT NULL,
  role           TEXT NOT NULL,
  adapter        TEXT NOT NULL DEFAULT 'claude_cli',
  model          TEXT,
  color          TEXT,
  icon           TEXT,
  prompt_extra   TEXT,
  allowed_states TEXT NOT NULL DEFAULT '[]',
  enabled        INTEGER NOT NULL DEFAULT 1,
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL
);
"""


_DEFAULT_AGENT_PROFILES = [
    {
        "profile_id": "haiku_worker",
        "display": "Haiku · Worker",
        "role": "HAIKU_WORKER",
        "adapter": "claude_cli",
        "model": "claude-haiku-4-5-20251001",
        "color": "#a78bfa",
        "icon": "🔨",
        "prompt_extra": None,
        "allowed_states": '["READY_FOR_WORKER","CHANGES_REQUESTED"]',
    },
    {
        "profile_id": "sonnet_manager",
        "display": "Sonnet · Manager / Reviewer",
        "role": "SONNET_MANAGER",
        "adapter": "claude_cli",
        "model": "claude-sonnet-4-6",
        "color": "#60a5fa",
        "icon": "🧭",
        "prompt_extra": None,
        "allowed_states": '["AWAITING_REVIEW","CHANGES_REQUESTED"]',
    },
    {
        "profile_id": "opus_auditor",
        "display": "Opus · Auditor",
        "role": "OPUS_AUDITOR",
        "adapter": "claude_cli",
        "model": "claude-opus-4-7",
        "color": "#f472b6",
        "icon": "🧠",
        "prompt_extra": None,
        "allowed_states": '["DONE","AUDIT_QUEUE","AWAITING_REVIEW"]',
    },
]


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        SETTINGS.db_path.parent.mkdir(parents=True, exist_ok=True)
        _conn = _connect(SETTINGS.db_path)
    return _conn


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    """Use for a write transaction. Commits on success, rolls back on error."""
    conn = get_conn()
    conn.execute("BEGIN")
    try:
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def init_db() -> None:
    """Run the DDL idempotently and stamp schema_version if empty."""
    conn = get_conn()
    conn.executescript(SCHEMA)
    row = conn.execute("SELECT COUNT(*) AS n FROM schema_version").fetchone()
    if row["n"] == 0:
        conn.execute(
            "INSERT INTO schema_version(version, applied_at) VALUES (?, datetime('now'))",
            (1,),
        )
    _seed_agent_profiles()


def _seed_agent_profiles() -> None:
    from datetime import datetime, timezone
    conn = get_conn()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for p in _DEFAULT_AGENT_PROFILES:
        exists = conn.execute(
            "SELECT 1 FROM agent_profiles WHERE profile_id=?", (p["profile_id"],)
        ).fetchone()
        if exists:
            continue
        conn.execute(
            """INSERT INTO agent_profiles
               (profile_id, display, role, adapter, model, color, icon,
                prompt_extra, allowed_states, enabled, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,1,?,?)""",
            (p["profile_id"], p["display"], p["role"], p["adapter"], p["model"],
             p["color"], p["icon"], p["prompt_extra"], p["allowed_states"],
             now, now),
        )


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None
