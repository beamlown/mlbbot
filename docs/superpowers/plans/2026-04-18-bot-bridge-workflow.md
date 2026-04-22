# BOT_BRIDGE Workflow + Control Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the approved workflow design (spec `2026-04-18-bot-bridge-workflow-design.md`) into the live system — a single canonical BOT_BRIDGE tree, enforced state machine, one writer per folder, rigid artifact schema, first-class patches, and a color-coded control-plane board that is the operator's only surface.

**Architecture:** Additive rather than replacing. Reuse existing `control_plane/` modules; extend rather than rewrite. Canonical tree stays at `mlbbot\BOT_BRIDGE\`. Existing lane names kept where possible (READY_FOR_WORKER, RUNNING, AWAITING_REVIEW, CHANGES_REQUESTED, DONE=APPROVED-staged, LIVE=SHIPPED, ARCHIVED) + add DRAFT and BLOCKED. New `task_events` table is the audit trail. Startup guardrails block the app if legacy tree has post-cutoff edits.

**Tech Stack:** Python 3.14, Flask, SQLite (WAL), Jinja2 templates, plain CSS. Claude CLI subprocess for agent runs (unchanged).

---

## File map

**Create:**
- `control_plane/startup_check.py` — 5 guardrails, banner summary
- `control_plane/routes/startup_check.py` — `/api/system/guardrails`
- `control_plane/permissions.py` — `can(role, action, target)` gate
- `control_plane/templates/_card.html` — reusable card partial (color-coded)

**Modify:**
- `control_plane/config.py` — add `BOT_SOURCE_ROOT`, `LEGACY_BRIDGE_ROOT`, `LEGACY_CUTOFF_TS`, `ARCHIVE_AFTER_DAYS`
- `control_plane/db.py` — new tables + columns (`task_events`, `quarantined_artifacts`, `tasks.attempt`, `tasks.age_first_seen`, `tasks.last_transition_ts`)
- `control_plane/workflow.py` — add DRAFT, BLOCKED lanes; compute `age_bucket`, `attempt_num`
- `control_plane/app.py` — wire startup_check; register new blueprint
- `control_plane/bridge/parsers.py` — writer-attribution header parse
- `control_plane/bridge/importer.py` — quarantine mover + task_events writer
- `control_plane/routes/actions.py` — can() gate; write task_events on mutations
- `control_plane/routes/system.py` — expose guardrail statuses
- `control_plane/templates/board.html` — use `_card.html`; loop-back lane for CHANGES_REQUESTED
- `control_plane/static/app.css` — new card classes (state hue, track stripe, age badge, priority border)
- `mlbbot\BOT_BRIDGE\` — create missing folders (`04_DRAFTS`, `08_PATCHES`, `10_ARCHIVE`, `99_QUARANTINE`)

**Verify via:**
- Control plane restart + `/system` page shows 5 green guardrail badges
- Create a task, watch card color change through state machine
- Drop a mis-named file in `06_OUTBOX`, confirm it routes to `99_QUARANTINE`

---

## Task order (critical path first)

1. Canonical folder structure on disk
2. Config constants + LEGACY_CUTOFF_TS
3. Startup guardrails module + route
4. DB: task_events + new tasks columns + quarantined_artifacts
5. workflow.py: add DRAFT + BLOCKED, derive `age_bucket` and `attempt_num`
6. Writer-attribution parser + quarantine mover
7. Permissions gate (`can()`) + wire into routes/actions.py
8. Board UI: card partial + CSS + loop-back lane
9. Verification end-to-end per spec §8

Each task below is a single commit.

---

### Task 1: Create the missing canonical folders

**Files:**
- Create: `mlbbot\BOT_BRIDGE\04_DRAFTS\.gitkeep`
- Create: `mlbbot\BOT_BRIDGE\08_PATCHES\.gitkeep`
- Create: `mlbbot\BOT_BRIDGE\08_PATCHES\PATCH_PENDING\.gitkeep`
- Create: `mlbbot\BOT_BRIDGE\10_ARCHIVE\.gitkeep`
- Create: `mlbbot\BOT_BRIDGE\99_QUARANTINE\.gitkeep`
- Create: `mlbbot\BOT_BRIDGE\00_START_HERE\README.md` (canonical readme; points at spec)
- Note: keep existing `08_SHARED_CONTEXT` for now; rename to `09_SHARED_CONTEXT` deferred to a separate cycle because 197 files + DB references would need a coordinated migration.

- [ ] **Step 1:** Create the 5 new folders with `.gitkeep` sentinels.
- [ ] **Step 2:** Write `00_START_HERE/README.md` with pointer to the spec + one-paragraph summary.
- [ ] **Step 3:** Verify structure (`ls mlbbot\BOT_BRIDGE\`).

---

### Task 2: Add config constants

**Files:**
- Modify: `control_plane/config.py`

- [ ] **Step 1:** Add fields `bot_source_root: Path`, `legacy_bridge_root: Path`, `legacy_cutoff_ts: float`, `archive_after_days: int`, `orphan_source_globs: tuple[str, ...]` to the `Settings` dataclass.
- [ ] **Step 2:** Default `bot_source_root = C:/Users/johnny/Desktop/sports_bot_v2`; `legacy_bridge_root = C:/Users/johnny/Desktop/BOT_BRIDGE`; `legacy_cutoff_ts = datetime(2026, 4, 18, 0, 0, 0).timestamp()`; `archive_after_days = 14`; `orphan_source_globs = ("C:/Users/johnny/Desktop/mlbbot/sports_bot_v2", "C:/Users/johnny/Desktop/mlbbot/sports_bot_v2.ORPHAN_ARCHIVE_*")`.
- [ ] **Step 3:** Env-var overrides: `CONTROL_PLANE_BOT_SOURCE_ROOT`, `CONTROL_PLANE_LEGACY_CUTOFF_TS`, `CONTROL_PLANE_ARCHIVE_AFTER_DAYS`.

---

### Task 3: Startup guardrails module

**Files:**
- Create: `control_plane/startup_check.py`

- [ ] **Step 1:** Define dataclass `GuardrailResult(name, ok, detail, violating_paths)`.
- [ ] **Step 2:** Implement `check_legacy_cutoff()` → walks `legacy_bridge_root`, returns FAIL if any mtime > `legacy_cutoff_ts`.
- [ ] **Step 3:** Implement `check_orphan_sources()` → glob `orphan_source_globs`; for each match, check for `runtime/bot.pid` with alive PID; FAIL if alive.
- [ ] **Step 4:** Implement `check_role_configs()` → grep `mlbbot/.claude-roles/*/CLAUDE.md` for legacy paths; WARN (not FAIL) if found, surface in banner.
- [ ] **Step 5:** Implement `check_bridge_structure()` → assert `BRIDGE_ROOT` exists and contains the required subfolders (01_RULES, 05_INBOX..., etc.); FAIL if missing.
- [ ] **Step 6:** Implement `check_single_bridge_root()` → assert `BRIDGE_ROOT == mlbbot/BOT_BRIDGE` (fixed guard against pointing to legacy by accident).
- [ ] **Step 7:** `run_all() -> list[GuardrailResult]` returns all 5. Startup calls this; if any is FAIL, prints to stderr and (unless `CONTROL_PLANE_FORCE_START=1`) raises.

---

### Task 4: DB migrations for state machine

**Files:**
- Modify: `control_plane/db.py`

- [ ] **Step 1:** Append to `SCHEMA`:
```sql
CREATE TABLE IF NOT EXISTS task_events (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id      TEXT NOT NULL,
  from_state   TEXT,
  to_state     TEXT NOT NULL,
  trigger      TEXT NOT NULL,
  actor        TEXT NOT NULL,
  attempt      INTEGER NOT NULL DEFAULT 1,
  artifact_path TEXT,
  detail       TEXT,
  created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_task_events_task ON task_events(task_id, created_at DESC);

CREATE TABLE IF NOT EXISTS quarantined_artifacts (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  original_path   TEXT NOT NULL,
  quarantine_path TEXT NOT NULL,
  reason          TEXT NOT NULL,
  detected_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_quarantine_time ON quarantined_artifacts(detected_at DESC);
```
- [ ] **Step 2:** In `init_db()` add:
```python
_add_column_if_missing(conn, "tasks", "attempt", "INTEGER NOT NULL DEFAULT 1")
_add_column_if_missing(conn, "tasks", "age_first_seen", "TEXT")
_add_column_if_missing(conn, "tasks", "last_transition_ts", "TEXT")
```
- [ ] **Step 3:** Helper `log_task_event(task_id, from_state, to_state, trigger, actor, artifact_path=None, detail=None)` that also bumps `tasks.last_transition_ts`.

---

### Task 5: workflow.py — add DRAFT, BLOCKED, age_bucket, attempt_num

**Files:**
- Modify: `control_plane/workflow.py`

- [ ] **Step 1:** Add `"DRAFT"` and `"BLOCKED"` to `WORKFLOW_LANES`. Display names: "Draft", "Blocked".
- [ ] **Step 2:** In `derive_state()`:
  - DRAFT if raw_status in (`DRAFT`, `PENDING`) **and** no artifact of kind HANDOFF exists for this task.
  - BLOCKED if raw_status in (`BLOCKED`) or `block_reason` is non-empty **and** there is no active run.
- [ ] **Step 3:** Add `derive_age_bucket(task) -> Literal["new","active","stale"]`:
  - `new` if `age_first_seen` within last 2 hours
  - `stale` if `last_transition_ts` older than 2 days and state ∈ {READY_FOR_WORKER, AWAITING_REVIEW, CHANGES_REQUESTED}
  - else `active`
- [ ] **Step 4:** `annotate(task)` augments with `workflow_state`, `age_bucket`, `attempt_num` (from `tasks.attempt`), `track` (from the first line of `HANDOFF` content if parseable, else `None`).

---

### Task 6: Writer-attribution header parser + quarantine

**Files:**
- Modify: `control_plane/bridge/parsers.py`
- Modify: `control_plane/bridge/importer.py`

- [ ] **Step 1:** In `parsers.py` add `parse_writer_header(text: str) -> dict | None`. Expects first line format: `<!-- writer: <role>, task_id: <TID>, patch_id: <PID|pending>, written_at: <iso>, attempt: <n> -->`. Returns `{writer, task_id, patch_id, written_at, attempt}` or `None`.
- [ ] **Step 2:** Define `EXPECTED_WRITER_BY_FOLDER = {"05_INBOX_FROM_MANAGER": {"manager","control_plane","operator"}, "06_OUTBOX_FROM_WORKER": {"worker"}, "07_REVIEWS": {"reviewer"}, "08_PATCHES": {"auditor","control_plane"}, "08_SHARED_CONTEXT": {"operator","control_plane","manager","auditor"}}`.
- [ ] **Step 3:** In `importer.py`, before upsert, call `_validate_writer(folder, file_path, content)`. On failure, move file to `99_QUARANTINE/<uuid>_<orig_name>`, insert row in `quarantined_artifacts`, skip upsert. Do NOT quarantine legacy files without headers in 08_SHARED_CONTEXT (those predate this rule).

---

### Task 7: Permissions gate

**Files:**
- Create: `control_plane/permissions.py`

- [ ] **Step 1:** Define `can(role: str, action: str, target: str | None = None) -> bool` with a matrix matching the role table in spec §4. Actions: `create_task`, `edit_task`, `claim_task`, `launch_run`, `write_result`, `write_review`, `write_audit`, `add_to_patch`, `ship_patch`, `unblock`, `cancel`, `archive`.
- [ ] **Step 2:** Export a helper `require(role, action, target=None)` that raises `PermissionError` with a useful message on fail.
- [ ] **Step 3:** Add a pytest-compatible smoke test (inline in module under `if __name__ == "__main__"`) covering operator/manager/worker/reviewer/auditor happy paths and one denial each.

---

### Task 8: Wire guardrails into startup + UI

**Files:**
- Modify: `control_plane/app.py`
- Modify: `control_plane/routes/system.py`
- Modify: `control_plane/templates/system.html`

- [ ] **Step 1:** In `app.py`, before `init_db()`, call `run_all()` from `startup_check`; print banner + raise on FAIL.
- [ ] **Step 2:** In `routes/system.py` add `/api/system/guardrails` → JSON of `GuardrailResult` list (cached 30s).
- [ ] **Step 3:** In `templates/system.html` add a top panel rendering each guardrail as a pass/fail badge with violating paths on hover.

---

### Task 9: Color-coded board UI

**Files:**
- Create: `control_plane/templates/_card.html`
- Modify: `control_plane/templates/board.html`
- Modify: `control_plane/static/app.css`

- [ ] **Step 1:** Create `_card.html` partial that renders a single task card with classes: `card state--<state>`, `track--<A|B|none>`, `age--<new|active|stale>`, `attempt--<1|2|3+>`, `priority--<CRITICAL|HIGH|MEDIUM|LOW>`.
- [ ] **Step 2:** Replace inline card markup in `board.html` with `{% include "_card.html" %}`.
- [ ] **Step 3:** Render the CHANGES_REQUESTED lane above the main lane strip as a dedicated loop-back row labelled "Rework".
- [ ] **Step 4:** In `app.css`, add:
  - `.state--READY_FOR_WORKER { background: #1e3a8a; /* deep blue */ }`
  - `.state--CLAIMED { background: #0f766e; /* teal */ }`
  - `.state--RUNNING { background: #b45309; animation: pulse 2s ease-in-out infinite; }`
  - `.state--AWAITING_REVIEW { background: #6d28d9; /* violet */ }`
  - `.state--DONE { background: #166534; /* green */ }`
  - `.state--CHANGES_REQUESTED { background: #c2410c; /* orange */ }`
  - `.state--BLOCKED { background: #991b1b; /* red */ }`
  - `.state--IN_PATCH { background: #a16207; /* gold */ }`
  - `.state--LIVE { background: #374151; /* grey */ }`
  - `.state--ARCHIVED { background: #1f2937; opacity: 0.55; }`
  - `.track--A::before { content:""; display:block; position:absolute; left:0; top:0; bottom:0; width:4px; background:#22d3ee; }`
  - `.track--B::before { ... background:#ec4899; }`
  - `.age--new .age-badge { background: #facc15; }` (yellow dot top-right)
  - `.age--stale .age-badge { background: #f59e0b; color:#000; }` (warning)
  - `.attempt--2, .attempt--3 { border: 2px dashed #fbbf24; }`
  - `.priority--CRITICAL { border-left-width: 6px; } .priority--HIGH { border-left-width: 4px; } .priority--MEDIUM { border-left-width: 2px; } .priority--LOW { border-left-width: 1px; }`
  - `@keyframes pulse { 0%,100% { filter: brightness(1); } 50% { filter: brightness(1.25); } }`

---

### Task 10: End-to-end verification

- [ ] **Step 1:** Kill and restart control plane. Visit `/system` → 5 guardrail badges green.
- [ ] **Step 2:** Visit `/` → board loads; new DRAFT lane visible if any DRAFT tasks exist; CHANGES_REQUESTED loop-back row renders above main row.
- [ ] **Step 3:** Drop a rogue file (e.g. `TEST_ROGUE.md` with no writer header) into `06_OUTBOX_FROM_WORKER\`. Hit `/api/import`. Confirm file moved to `99_QUARANTINE\` and row in `quarantined_artifacts`.
- [ ] **Step 4:** Touch a file in legacy `Desktop\BOT_BRIDGE\` (`echo "test" > test.md`). Restart control plane. Confirm startup refuses with legacy-cutoff violation. Remove the file; restart succeeds.
- [ ] **Step 5:** Manually set a task's `attempt=2` and state to `CHANGES_REQUESTED`; confirm card shows dashed border + "2" badge.

---

## Self-review

- **Spec coverage:**
  - §2 canonical folders + guardrails → Tasks 1, 2, 3, 8
  - §3 state machine → Tasks 4, 5 (DB + derivation); transition enforcement in routes is deferred to a follow-up because current routes already derive state rather than mutate it
  - §4 role permissions → Task 7 (module landed; route wiring deferred)
  - §5 artifact schema → Task 6 (writer-attribution parser); content schema validation deferred (current parsers already do basic classification)
  - §6 patches as folders → NOT in this plan (existing patches-as-DB-rows keeps working; folder-per-patch is a separate plan once the state machine is stable)
  - §7 control plane wiring + color board → Tasks 8, 9
  - §8 verification → Task 10

- **Placeholder scan:** none.
- **Type consistency:** `GuardrailResult`, `task_events` columns, `can(role, action, target)` signature consistent across tasks.

Follow-up plan (not in this execution): content schema validators, role-permission wiring into every mutation route, folder-per-patch refactor, archive rotation cron, audit/task_events viewer page.
