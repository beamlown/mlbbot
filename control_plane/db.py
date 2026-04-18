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


SCHEMA = r"""
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

CREATE TABLE IF NOT EXISTS patches (
  patch_id    TEXT PRIMARY KEY,
  version     TEXT NOT NULL UNIQUE,
  status      TEXT NOT NULL DEFAULT 'PENDING',   -- PENDING | SHIPPED
  title       TEXT,
  notes       TEXT,
  created_at  TEXT NOT NULL,
  shipped_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_patches_status ON patches(status);

-- patch_reviews: orchestrator state for a per-task-sequential Opus review
-- of a whole patch. One row per (patch_id) — status advances pending →
-- in_progress → done|failed. `current_index` points at the next step to
-- launch; `summaries_json` is an array of TL;DR bullets carried forward
-- into each subsequent step's prompt; `run_ids_json` records the Opus
-- run per step for audit; `failed_steps_json` marks steps skipped due to
-- non-zero exit so synthesis can flag them.
CREATE TABLE IF NOT EXISTS patch_reviews (
  patch_id          TEXT PRIMARY KEY,
  status            TEXT NOT NULL DEFAULT 'pending',
  current_index     INTEGER NOT NULL DEFAULT 0,
  total_steps       INTEGER NOT NULL DEFAULT 0,
  summaries_json    TEXT NOT NULL DEFAULT '[]',
  run_ids_json      TEXT NOT NULL DEFAULT '[]',
  failed_steps_json TEXT NOT NULL DEFAULT '[]',
  synthesis_run_id  TEXT,
  final_decision    TEXT,
  started_at        TEXT NOT NULL,
  finished_at       TEXT,
  FOREIGN KEY (patch_id) REFERENCES patches(patch_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_patch_reviews_status ON patch_reviews(status);

-- known_files: file index across mlbbot and its sibling project roots
-- (sports_bot_v2, mlb_model, march_madness_bot). Populated by a
-- startup scan; used by the prompt builder to resolve bare filenames
-- in allowed_files to their canonical absolute paths so agents stop
-- Glob/Grep'ing entire trees. Scanner skips junk dirs (.git, __pycache__,
-- node_modules, .venv) and files larger than ~1MB.
CREATE TABLE IF NOT EXISTS known_files (
  abs_path   TEXT PRIMARY KEY,
  basename   TEXT NOT NULL,
  root       TEXT NOT NULL,
  kind       TEXT,
  size_bytes INTEGER,
  mtime      INTEGER,
  indexed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_known_files_basename ON known_files(basename);
CREATE INDEX IF NOT EXISTS idx_known_files_root     ON known_files(root);

-- task_events: audit trail for every state transition. One row per
-- transition; `actor` names the role or subsystem that triggered it
-- (e.g. "worker", "reviewer", "control_plane", "operator"). This is the
-- single source of truth for "why did this task move?"
CREATE TABLE IF NOT EXISTS task_events (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id       TEXT NOT NULL,
  from_state    TEXT,
  to_state      TEXT NOT NULL,
  trigger       TEXT NOT NULL,
  actor         TEXT NOT NULL,
  attempt       INTEGER NOT NULL DEFAULT 1,
  artifact_path TEXT,
  detail        TEXT,
  created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_task_events_task ON task_events(task_id, created_at DESC);

-- quarantined_artifacts: files that landed in the wrong folder or lacked
-- a writer-attribution header. Importer moves them to 99_QUARANTINE\ and
-- records the original path + reason so the operator can inspect.
CREATE TABLE IF NOT EXISTS quarantined_artifacts (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  original_path   TEXT NOT NULL,
  quarantine_path TEXT NOT NULL,
  reason          TEXT NOT NULL,
  detected_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_quarantine_time ON quarantined_artifacts(detected_at DESC);
"""


_DEFAULT_AGENT_PROFILES = [
    {
        "profile_id": "haiku_worker",
        "display": "Haiku",
        "role": "HAIKU_WORKER",
        "adapter": "claude_cli",
        "model": "claude-haiku-4-5-20251001",
        "color": "#a78bfa",
        "icon": "🔨",
        "tagline": "The Apprentice — fast hands, tight scope, makes the change and gets out.",
        "prompt_extra": None,
        "allowed_states": '["READY_FOR_WORKER","CHANGES_REQUESTED"]',
    },
    {
        "profile_id": "sonnet_manager",
        "display": "Sonnet",
        "role": "SONNET_MANAGER",
        "adapter": "claude_cli",
        "model": "claude-sonnet-4-6",
        "color": "#60a5fa",
        "icon": "🧭",
        "tagline": "The Steward — reads the room, weighs the work, signs off or sends it back.",
        "prompt_extra": None,
        "allowed_states": '["AWAITING_REVIEW","CHANGES_REQUESTED"]',
    },
    {
        "profile_id": "opus_auditor",
        "display": "Opus",
        "role": "OPUS_AUDITOR",
        "adapter": "claude_cli",
        "model": "claude-opus-4-7",
        "color": "#f472b6",
        "icon": "🧠",
        "tagline": "The Oracle — deep read, sharp eyes, surfaces what others missed.",
        "prompt_extra": None,
        "allowed_states": '["DONE","AUDIT_QUEUE","AWAITING_REVIEW"]',
    },
    {
        # Sole Opus gate before ship. Launched from the patch detail view
        # via POST /api/patches/<pid>/review; not attached to any task lane.
        "profile_id": "opus_patch_reviewer",
        "display": "Opus · Patch",
        "role": "OPUS_PATCH_REVIEWER",
        "adapter": "claude_cli",
        "model": "claude-opus-4-7",
        "color": "#fb7185",
        "icon": "📜",
        "tagline": "The Magistrate — reads the whole patch, one task at a time, then renders the verdict.",
        "prompt_extra": None,
        "allowed_states": "[]",
    },
    {
        # Cheap semantic gate auto-launched after a worker RESULT passes the
        # deterministic structural check. Not user-selectable in the task
        # launch dropdown; the dispatcher spawns it directly.
        "profile_id": "sonnet_triage",
        "display": "Sonnet · Triage",
        "role": "SONNET_TRIAGE",
        "adapter": "claude_cli",
        "model": "claude-sonnet-4-6",
        "color": "#34d399",
        "icon": "🔎",
        "tagline": "The Gatekeeper — one question, one answer: did the worker do what was asked?",
        "prompt_extra": None,
        "allowed_states": "[]",
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


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    """SQLite-friendly equivalent of ADD COLUMN IF NOT EXISTS."""
    cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


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
    # Forward-migrate agent_profiles with the gamification fields.
    _add_column_if_missing(conn, "agent_profiles", "tagline", "TEXT")
    # Patch bundling — DONE tasks stack into a pending patch, shipped on relaunch.
    _add_column_if_missing(conn, "tasks", "patch_id", "TEXT")
    # Patch-review ordering (manual reorder from patch detail UI).
    _add_column_if_missing(conn, "tasks", "patch_order", "INTEGER NOT NULL DEFAULT 0")
    # "Why stuck" signal + dependency-based parking.
    _add_column_if_missing(conn, "tasks", "blocked_on", "TEXT")
    _add_column_if_missing(conn, "tasks", "block_reason", "TEXT")
    _add_column_if_missing(conn, "tasks", "blocked_at", "TEXT")
    # JSON-encoded meta tagging a run as part of a patch-review step.
    # Shape: {"patch_id": "PATCH_X", "step": 3, "total": 7} for a per-task
    # step, or {"patch_id": "PATCH_X", "synthesis": true} for the final.
    # capture.py reads this to route the finalize hook to the orchestrator.
    _add_column_if_missing(conn, "runs", "patch_review_meta", "TEXT")
    # State-machine telemetry (added 2026-04-18):
    #   attempt            — rework counter (1 on create, ++ on re-open)
    #   age_first_seen     — iso timestamp the task was first imported/created
    #   last_transition_ts — iso timestamp of the most recent state change
    _add_column_if_missing(conn, "tasks", "attempt", "INTEGER NOT NULL DEFAULT 1")
    _add_column_if_missing(conn, "tasks", "age_first_seen", "TEXT")
    _add_column_if_missing(conn, "tasks", "last_transition_ts", "TEXT")
    # Roster gamification (added 2026-04-18, Dugout OS):
    #   status           — ACTIVE | RELEASED
    #   signed_at        — iso ts when persona joined the roster
    #   released_at      — iso ts when persona was released (NULL if active)
    #   released_reason  — operator-supplied reason
    #   jersey_number    — unique number across all rows (active + released)
    _add_column_if_missing(conn, "agent_profiles", "status",
                           "TEXT NOT NULL DEFAULT 'ACTIVE'")
    _add_column_if_missing(conn, "agent_profiles", "signed_at",      "TEXT")
    _add_column_if_missing(conn, "agent_profiles", "released_at",    "TEXT")
    _add_column_if_missing(conn, "agent_profiles", "released_reason","TEXT")
    _add_column_if_missing(conn, "agent_profiles", "jersey_number",  "INTEGER")
    # Dugout OS — restart-scope on tasks (added 2026-04-18):
    #   none           — hot change; already live the moment it's approved
    #                    (docs, spec, dashboard cosmetic, CSS-only).
    #   control_plane  — needs the CP Flask process relaunched.
    #   bot            — needs the betting bot process relaunched.
    #   both           — needs both. Safe default; anything touching shared
    #                    modules or data models.
    _add_column_if_missing(conn, "tasks", "restart_scope",
                           "TEXT NOT NULL DEFAULT 'both'")
    _backfill_restart_scope()
    _backfill_roster_fields()
    _seed_agent_profiles()


def log_task_event(
    task_id: str,
    from_state: str | None,
    to_state: str,
    trigger: str,
    actor: str,
    artifact_path: str | None = None,
    detail: str | None = None,
    attempt: int | None = None,
) -> None:
    """Write a row to `task_events` and update `tasks.last_transition_ts`.

    Called from importer (on detected state change) and from routes/actions
    (on operator-driven mutations). Idempotency is the caller's problem —
    this just appends.
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = get_conn()
    # Resolve attempt from the task row if not supplied.
    if attempt is None:
        row = conn.execute(
            "SELECT attempt FROM tasks WHERE task_id=?", (task_id,)
        ).fetchone()
        attempt = (row["attempt"] if row and "attempt" in row.keys() else 1) or 1
    conn.execute(
        """INSERT INTO task_events
           (task_id, from_state, to_state, trigger, actor, attempt,
            artifact_path, detail, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (task_id, from_state, to_state, trigger, actor, attempt,
         artifact_path, detail, now),
    )
    conn.execute(
        "UPDATE tasks SET last_transition_ts=? WHERE task_id=?",
        (now, task_id),
    )


_DEFAULT_JERSEYS = {
    "haiku_worker":         7,
    "sonnet_manager":       42,
    "sonnet_triage":        11,
    "opus_auditor":         99,
    "opus_patch_reviewer":  1,
}


_VALID_RESTART_SCOPES = frozenset({"none", "control_plane", "bot", "both"})


_RESTART_SCOPE_HINTS = (
    # (substring match on lowercased subsystem, resulting scope)
    ("docs",           "none"),
    ("doc",            "none"),
    ("spec",           "none"),
    ("notes",          "none"),
    ("dashboard",      "control_plane"),
    ("control_plane",  "control_plane"),
    ("ui",             "control_plane"),
    ("template",       "control_plane"),
    ("css",            "none"),
    ("bot",            "bot"),
    ("runner",         "bot"),
    ("sports_bot",     "bot"),
    ("mlb_model",      "bot"),
    ("ingest",         "bot"),
    ("sizing",         "bot"),
    ("decision",       "bot"),
    ("baseball",       "bot"),
)


def _restart_scope_for_subsystem(subsystem: str | None) -> str:
    """Heuristic guess for a task's restart scope from its subsystem label.

    Returns 'none' | 'control_plane' | 'bot' | 'both'. Safe default is 'both';
    operators can always override in the UI.
    """
    s = (subsystem or "").strip().lower()
    if not s:
        return "both"
    for needle, scope in _RESTART_SCOPE_HINTS:
        if needle in s:
            return scope
    return "both"


def _backfill_restart_scope() -> None:
    """Populate restart_scope for tasks that pre-date the column.

    Only touches rows where restart_scope is NULL or the SQL-level default
    ('both') AND the subsystem gives a confident hint. If the heuristic
    returns 'both', we leave the row as-is (no signal either way).
    """
    conn = get_conn()
    rows = conn.execute(
        "SELECT task_id, subsystem, restart_scope FROM tasks"
    ).fetchall()
    for r in rows:
        current = (r["restart_scope"] or "both").strip().lower()
        if current != "both":
            continue  # operator-edited; don't override
        guess = _restart_scope_for_subsystem(r["subsystem"])
        if guess == "both":
            continue  # no confident hint; leave default
        conn.execute(
            "UPDATE tasks SET restart_scope=? WHERE task_id=?",
            (guess, r["task_id"]),
        )


def _backfill_roster_fields() -> None:
    """One-time seed of cosmetic columns for personas that pre-date the migration.

    - status: leave 'ACTIVE' default; nothing to do.
    - signed_at: earliest run.created_at with this profile_id, else now().
    - jersey_number: pull from _DEFAULT_JERSEYS, else min unused 1..99.
    """
    from datetime import datetime, timezone
    conn = get_conn()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = conn.execute(
        "SELECT profile_id, signed_at, jersey_number FROM agent_profiles"
    ).fetchall()
    used = {r["jersey_number"] for r in rows if r["jersey_number"] is not None}
    for r in rows:
        pid = r["profile_id"]
        if not r["signed_at"]:
            earliest = conn.execute(
                "SELECT MIN(created_at) AS t FROM runs WHERE role IN "
                "(SELECT role FROM agent_profiles WHERE profile_id=?)",
                (pid,),
            ).fetchone()
            signed = (earliest["t"] if earliest and earliest["t"] else now)
            conn.execute(
                "UPDATE agent_profiles SET signed_at=? WHERE profile_id=?",
                (signed, pid),
            )
        if r["jersey_number"] is None:
            jn = _DEFAULT_JERSEYS.get(pid)
            if jn is None or jn in used:
                jn = next(n for n in range(1, 100) if n not in used)
            conn.execute(
                "UPDATE agent_profiles SET jersey_number=? WHERE profile_id=?",
                (jn, pid),
            )
            used.add(jn)


def _seed_agent_profiles() -> None:
    from datetime import datetime, timezone
    conn = get_conn()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for p in _DEFAULT_AGENT_PROFILES:
        exists = conn.execute(
            "SELECT 1 FROM agent_profiles WHERE profile_id=?", (p["profile_id"],)
        ).fetchone()
        if exists:
            # Fill in the tagline for pre-migration profiles without touching
            # operator-edited fields. This keeps the gamification bits fresh
            # across updates while leaving model/color/etc. alone.
            if p.get("tagline"):
                conn.execute(
                    "UPDATE agent_profiles SET tagline=? WHERE profile_id=? AND (tagline IS NULL OR tagline='')",
                    (p["tagline"], p["profile_id"]),
                )
            # Also refresh display/icon if they still match the old seed so
            # the UI picks up the new short names (Haiku/Sonnet/Opus) without
            # overwriting an operator-customised label.
            if p.get("display"):
                conn.execute(
                    "UPDATE agent_profiles SET display=? "
                    "WHERE profile_id=? AND display IN (?, ?, ?)",
                    (p["display"], p["profile_id"],
                     "Haiku · Worker", "Sonnet · Manager / Reviewer", "Opus · Auditor"),
                )
            continue
        conn.execute(
            """INSERT INTO agent_profiles
               (profile_id, display, role, adapter, model, color, icon, tagline,
                prompt_extra, allowed_states, enabled, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,1,?,?)""",
            (p["profile_id"], p["display"], p["role"], p["adapter"], p["model"],
             p["color"], p["icon"], p.get("tagline"), p["prompt_extra"],
             p["allowed_states"], now, now),
        )


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None
