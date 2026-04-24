# CONTROL_PLANE_IMPLEMENTATION_PLAN.md

BOT_BRIDGE Control Plane — local browser-based dashboard that replaces the
Claude Code terminal as the primary interface for managing tasks, runs,
artifacts, reviews, and role flow (Opus / Sonnet / Haiku).

Target: single operator, localhost only, cross-platform (Linux dev sandbox +
Windows primary operator box).

---

## Scope

In scope:
- Task board (ACTIVE / QUEUED / BLOCKED / DONE / BACKLOG) with create / edit /
  assign / transition / review actions.
- Task detail view (brief, acceptance criteria, allowed/forbidden files,
  linked artifacts, run history, review flow).
- Run / session viewer — active, queued, completed, failed runs; live logs
  via SSE; cancel / retry; link result to task.
- Artifact viewer — HANDOFF / RESULT / REVIEW / APPROVED / SPEC / AUDIT /
  STATUS / BOARD markdown or JSON, rendered + raw.
- System / runtime panel — `runtime/state.json`, process stack, config hash,
  bot on/off flag, paper-only flag.
- Role-based launching with a capability table — Opus architect / auditor /
  reviewer, Sonnet manager, Haiku worker. Server-side enforcement.
- Round-trip integration with `BOT_BRIDGE/` — DB is source of truth, files
  are exported artifacts.

Out of scope (for now):
- Multi-user auth (single operator, loopback-bound).
- Cloud sync.
- Any change to `sports_bot_v2/` runtime code or `mlb_model/` training.
- Replacing the existing trading dashboard on port 8900.

---

## Architecture

Stack:
- Python 3.11+
- Flask + Jinja2 (stdlib-adjacent; one `pip install flask` on the operator box)
- SQLite (stdlib `sqlite3`) with WAL mode
- Vanilla HTML + light JS (fetch + SSE). Tailwind via CDN for styling.
  No npm, no bundler.

Layout:
```
/home/user/mlbbot/                   ← repo root
  control_plane/                     ← new package
    __main__.py                      ← python -m control_plane
    app.py                           ← Flask app factory
    config.py                        ← paths, port, role defaults
    db.py                            ← sqlite connection + DDL + migrations
    models.py                        ← dataclasses for Task / Run / Review / Artifact
    roles.py                         ← role enum + capability table
    bridge/
      parsers.py                     ← TASK_*.json, RESULT_*.json, REVIEW_*.md, HANDOFF_*.md, CLAUDE_TASK_BOARD.md
      importer.py                    ← import_bot_bridge(): fs → DB
      exporter.py                    ← export_task(): DB → fs (Phase 2)
      task_board_md.py               ← regenerate CLAUDE_TASK_BOARD.md (Phase 2)
    runner/                          ← Phase 3
      base.py                        ← RunnerAdapter ABC
      dryrun.py                      ← DryRunAdapter
      file_handoff.py                ← FileHandoffAdapter
      claude_cli.py                  ← ClaudeCliAdapter
      prompts/                       ← Jinja templates per role
    routes/
      tasks.py                       ← board + task detail + task API
      artifacts.py                   ← artifact viewer
      runs.py                        ← run launch / cancel / SSE stream
      reviews.py                     ← review decisions
      system.py                      ← runtime state panel
    templates/
      base.html, board.html, task_detail.html, artifact.html,
      run_detail.html, system.html, partials/*.html
    static/app.css
    data/                            ← gitignored
      control_plane.db
      runs/<run_id>/stdout.log
    README.md
```

Port: **8787** (env override `CONTROL_PLANE_PORT`). Does not collide with the
existing trading dashboard on 8900. Binds to `127.0.0.1`.

Source-of-truth model:
- **DB is canonical** for task state, run history, reviews, comments.
- **Files (`BOT_BRIDGE/05..08/`) are exported artifacts** and the human-readable
  trail. The app imports them at startup and on demand; the app writes them
  on explicit mutation actions with a hash-based conflict check.

---

## Page list

| Path                         | Purpose |
|------------------------------|---------|
| `/`                          | Task board, five lanes, filter + search |
| `/tasks/<task_id>`           | Task detail — brief, ACs, allowed files, linked artifacts, runs, reviews |
| `/tasks/new`                 | Create-task form (role-gated to Opus/Sonnet) |
| `/artifacts/`                | Artifact browser + search |
| `/artifacts/<artifact_id>`   | Render single artifact (markdown or JSON), raw toggle |
| `/runs/`                     | Run list — active / queued / completed / failed |
| `/runs/<run_id>`             | Run detail — prompt, live log (SSE), cancel button |
| `/system`                    | Runtime state — state.json summary, process stack, config hash, on/off |
| `/api/...`                   | JSON APIs backing all HTMX / fetch calls |
| `/api/runs/<run_id>/stream`  | `text/event-stream` SSE live log |

---

## SQLite tables

See `control_plane/db.py` for authoritative DDL. Summary:

- `tasks` — one row per task. Mirrors `TASK_*.json` plus dashboard metadata
  (`assigned_role`, `lane_order`, `external_hash`, `external_mtime`,
  `conflict`).
- `runs` — one row per launched session. Fields: role, adapter, status, pid,
  prompt snapshot, stdout/stderr paths, exit code.
- `run_logs` — append-only log lines per run (replay + SSE cursor).
- `artifacts` — every on-disk BOT_BRIDGE file. Fields: kind, path, sha256,
  mtime, cached content.
- `task_artifacts` — many-to-many link (task ↔ artifact with `relation`:
  brief / handoff / result / review / reference).
- `reviews` — structured decisions (APPROVED / CHANGES_REQUESTED / FAIL /
  PROVISIONAL) linked to tasks and runs; review body lives as artifact.
- `comments` — operator notebook on tasks / runs / reviews.
- `settings` — kv for runtime config (bot on/off, paper-only, acting role).
- `schema_version` — migration tracking.

---

## API routes

Phase 1 (read-only mirror):
- `GET /` → board page
- `GET /tasks/<task_id>` → detail page
- `GET /api/tasks?status=...&subsystem=...&priority=...` → JSON task list
- `GET /api/tasks/<task_id>` → JSON task
- `GET /api/import/status` → last import timestamp + counts
- `POST /api/import` → re-scan BOT_BRIDGE/ into DB

Phase 2 (write round-trip):
- `POST /api/tasks` → create
- `PATCH /api/tasks/<task_id>` → edit
- `POST /api/tasks/<task_id>/transition` → move status (with lane_order)
- `POST /api/tasks/<task_id>/assign` → set role
- `POST /api/tasks/<task_id>/export` → write TASK_*.json + HANDOFF_*.md
- `POST /api/board/regenerate` → rewrite CLAUDE_TASK_BOARD.md

Phase 3 (runner):
- `POST /api/runs` → launch (task_id, role, adapter)
- `GET  /api/runs?status=...`
- `GET  /api/runs/<run_id>`
- `GET  /api/runs/<run_id>/stream` → SSE
- `POST /api/runs/<run_id>/cancel`
- `POST /api/runs/<run_id>/retry`

Phase 4 (reviews + roles):
- `POST /api/reviews` → create review with decision
- `POST /api/settings/acting_role` → switch operator role

Phase 5 (system panel):
- `GET /api/system/state` → parsed `runtime/state.json`
- `GET /api/system/processes` → process snapshot (psutil if available)
- `GET /api/system/config_hash` → latest config hash

---

## Phased implementation order

**Phase 1 — Read-only mirror (this PR).**
App skeleton, DB init, BOT_BRIDGE importer, board page, task detail page,
artifact read-through. Safe: no writes to disk, no external process launch.

**Phase 2 — Write round-trip.**
Create / edit / transition tasks in the UI, exporter that writes
`TASK_*.json` + `HANDOFF_*.md` + regenerates `CLAUDE_TASK_BOARD.md`.
Hash-based conflict check against on-disk edits.

**Phase 3 — Runner + SSE.**
`RunnerAdapter` abstract + three concrete adapters (DryRun, FileHandoff,
ClaudeCli). Per-role Jinja prompt templates. Run detail page with live log
via SSE. Cancel / retry.

**Phase 4 — Roles + permissions.**
Capability table in `roles.py` enforced by a Flask dependency. Acting-role
cookie. Worker file-write guard (reject RESULT that touches files outside
`allowed_files`).

**Phase 5 — Runtime / system panel.**
Read `sports_bot_v2/runtime/state.json`, surface config_hash, process stack
(psutil), bot on/off and paper-only toggles wired to settings + an optional
signal file the bot can consume.

**Phase 6 — Polish.**
Filewatch (watchdog) for external edits, conflict-resolution UI, full-text
artifact search, backup/export, packaged README, Windows quickstart script.
