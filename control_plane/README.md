# BOT_BRIDGE Control Plane

Local browser-based dashboard for the BOT_BRIDGE workflow. One operator,
localhost only. Replaces the Claude Code terminal as the primary interface for
managing tasks, runs, artifacts, reviews, and Opus / Sonnet / Haiku role flow.

## Quickstart

```bash
# 1. Install the one dependency (Flask). Python 3.11+ required.
pip install flask

# 2. From the repo root (the folder that contains BOT_BRIDGE/):
python -m control_plane

# 3. Open http://127.0.0.1:8787 in a browser.
```

On first launch the app:
1. Creates `control_plane/data/control_plane.db` (SQLite + WAL).
2. Scans `BOT_BRIDGE/05..08/` and imports every `TASK_*.json`,
   `HANDOFF_*.md`, `RESULT_*.json`, `REVIEW_*.md`, `APPROVED_*.md`,
   `PROVISIONAL_REVIEW_*.md`, spec, audit, board, and status file.
3. Reconciles `CLAUDE_TASK_BOARD.md` lane placements on top of the JSON-sourced
   task rows.

Port is `8787` by default (does not collide with the trading dashboard on
`8900`). Set `CONTROL_PLANE_PORT=9000` to change it.

## Environment

| Var | Default | Purpose |
|---|---|---|
| `CONTROL_PLANE_HOST`          | `127.0.0.1` | bind address |
| `CONTROL_PLANE_PORT`          | `8787`       | bind port |
| `CONTROL_PLANE_DATA_DIR`      | `control_plane/data` | DB + run-log storage |
| `CONTROL_PLANE_REPO_ROOT`     | (auto) | override the detected repo root |
| `CONTROL_PLANE_BRIDGE_ROOT`   | `<repo>/BOT_BRIDGE` | override BOT_BRIDGE path |
| `CONTROL_PLANE_DEFAULT_ROLE`  | `SONNET_MANAGER` | initial acting role |
| `CONTROL_PLANE_CLAUDE_BIN`    | `claude` | CLI binary for Phase 3 adapter |
| `CONTROL_PLANE_DEBUG`         | `0` | set `1` for Flask debug mode |

## What works now (Phase 1)

- **Board page** at `/` — five-lane Kanban populated from the existing
  `BOT_BRIDGE/` state. Filter by priority / subsystem, search by id/title.
- **Task detail** at `/tasks/<TASK_ID>` — rendered brief, allowed/forbidden
  files, linked artifacts, (empty) runs and reviews.
- **Artifact browser** at `/artifacts/` with kind filter + search; single
  artifact view at `/artifacts/<id>` with raw content.
- **System panel** at `/system` reads `sports_bot_v2/runtime/state.json` when
  present.
- **Re-import** button in the top bar re-scans `BOT_BRIDGE/` without a restart.

## What is stubbed (future phases)

- Phase 2 — creating / editing / transitioning tasks from the UI with
  round-trip export back to `TASK_*.json` + `HANDOFF_*.md` +
  `CLAUDE_TASK_BOARD.md`.
- Phase 3 — runner adapters (DryRun / FileHandoff / ClaudeCli), SSE live logs,
  cancel / retry.
- Phase 4 — role capability enforcement, acting-role switch from the top bar,
  Opus / Sonnet / Haiku prompt templates, worker file-write guard.
- Phase 5 — live bot on/off, config_hash, process stack, paper-only toggle.
- Phase 6 — filewatch, conflict resolution UI, full-text search, backup.

Each phase is self-contained and safe to ship one at a time.

## Design

- **Stack**: Flask + Jinja + stdlib `sqlite3` + vanilla CSS. No build step.
- **Source of truth**: the SQLite DB. Files in `BOT_BRIDGE/` are exported
  artifacts and the human-readable audit trail.
- **Round-trip**: importer pulls files → DB at startup and on demand; exporter
  (Phase 2) writes files back on explicit mutation actions with a
  hash-conflict check.
- **Cross-platform**: `pathlib`-everywhere. Runs identically on Linux and
  Windows.

See `../CONTROL_PLANE_IMPLEMENTATION_PLAN.md` for the full plan, schemas, and
API surface.
