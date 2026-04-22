# BOT_BRIDGE Workflow + Control Plane Unification — Design Spec

**Date:** 2026-04-18
**Author:** operator (johnny) + Claude
**Status:** approved design, ready for planning
**Scope:** redefine the end-to-end workflow across BOT_BRIDGE + control-plane (port 8787) so role boundaries, state transitions, artifact schema, and patch grouping are unambiguous and drift-resistant.

---

## 1. Context / Why

After the 2026-04-18 filetree-drift incident (two `sports_bot_v2` source trees running in parallel, two `BOT_BRIDGE` trees, `01_RULES` orphaned on the legacy path), the operator identified four simultaneous failure modes in the current workflow:

- **Role boundaries are fuzzy.** Manager / operator / reviewer / auditor overlap; unclear who owns HANDOFF authorship, patch closure, source edits.
- **State transitions are fuzzy.** Tasks get stuck between `READY_FOR_WORKER`, `RUNNING`, `AWAITING_REVIEW`; duplicate claims occur; re-work is invisible.
- **Artifact schema is fuzzy.** `TASK_*.json` (control-plane auto-export) coexists with `HANDOFF_*.md` (prose brief). Unclear which is the source of truth.
- **Patch grouping is fuzzy.** Shared-context folder is a catch-all; audit files float free of any patch manifest.

Plus the root cause behind the drift: **nothing prevents copies of the canonical tree from being created and edited in parallel.**

Intended outcome: one canonical tree, a single enforceable state machine, one writer per folder, rigid artifact schema, first-class patches, and a control-plane UI that is the operator's only surface — with color-coded cards that reveal state / category / age / attempt at a glance.

---

## 2. Canonical filetree + anti-drift guardrails

**Single canonical BOT_BRIDGE root:** `C:\Users\johnny\Desktop\mlbbot\BOT_BRIDGE\`
**Single canonical bot source root:** `C:\Users\johnny\Desktop\sports_bot_v2\`

**Folder layout:**

```
mlbbot\BOT_BRIDGE\
├── 00_START_HERE\         README for humans
├── 01_RULES\              doctrine (the 4 rule files)
├── 02_PROMPTS\            role prompt scaffolds consumed by control_plane\runner\prompts.py
├── 03_TEMPLATES\          TASK/RESULT/REVIEW/HANDOFF templates
├── 04_DRAFTS\             operator scratchpad; promoted into 05 by control plane
├── 05_INBOX_FROM_MANAGER\ writer: manager / control plane ONLY
├── 06_OUTBOX_FROM_WORKER\ writer: worker ONLY
├── 07_REVIEWS\            writer: reviewer ONLY
├── 08_PATCHES\            writer: auditor / control plane ONLY; one subfolder per patch
├── 09_SHARED_CONTEXT\     cross-cutting state (task board MD, session journal, audit indexes)
├── 10_ARCHIVE\            writer: control plane ONLY; auto-rotated from 05–08 after SHIPPED + N days
└── 99_QUARANTINE\         writer: control plane ONLY; rogue / mis-placed files land here
```

Differences vs current: `04_DRAFTS` (new, replaces empty `04_QUEUE`), `08_PATCHES` (new, promoted from mixed-use shared context), `09_SHARED_CONTEXT` (renumbered from 08), `10_ARCHIVE` (canonical archive location), `99_QUARANTINE` (new enforcement sink).

**Anti-drift guardrails (enforced on control-plane startup + every import):**

1. **Legacy-tree cutoff assertion.** If `Desktop\BOT_BRIDGE\` has any file modified after `2026-04-18 00:00:00`, refuse to start and print violating paths.
2. **Sibling-tree assertion.** Refuse to start if `mlbbot\sports_bot_v2\` or `mlbbot\sports_bot_v2.ORPHAN_ARCHIVE_*\` contains a `bot.pid` whose PID is alive.
3. **Writer-attribution header.** Every artifact file begins with `<!-- writer: <role_id>, task_id: <TID>, patch_id: <PID>, written_at: <iso>, attempt: <n> -->`. Parser rejects mismatches to `99_QUARANTINE\` with reason.
4. **Role CLAUDE.md lint.** Grep `.claude-roles/*/CLAUDE.md` for `Desktop\BOT_BRIDGE\` or `mlbbot\sports_bot_v2\` references → loud banner.
5. **Single `BRIDGE_ROOT` env var.** Control plane + all prompt builders pull the path from one `config.py` constant.

---

## 3. State machine

Only these 10 states are legal:

`DRAFT → READY_FOR_WORKER → CLAIMED → RUNNING → AWAITING_REVIEW → APPROVED | CHANGES_REQUESTED | BLOCKED → IN_PATCH → SHIPPED → ARCHIVED`

**Transition table (one legal trigger each):**

| From → To | Trigger | Owner |
|---|---|---|
| ∅ → DRAFT | "New Task" form or drop in `04_DRAFTS\` | operator / manager |
| DRAFT → READY_FOR_WORKER | control plane writes `05_INBOX\HANDOFF_<TID>.md` + `TASK_<TID>.json` | control plane ("Promote to Inbox") |
| READY_FOR_WORKER → CLAIMED | worker renames HANDOFF → `HANDOFF_<TID>.md.claimed` | worker |
| CLAIMED → RUNNING | run row created | control plane (launch) |
| RUNNING → AWAITING_REVIEW | worker writes RESULT with `status=ok` | worker |
| RUNNING → BLOCKED | worker writes RESULT with `status=blocked` | worker |
| AWAITING_REVIEW → APPROVED / CHANGES_REQUESTED / BLOCKED | reviewer writes REVIEW with `DECISION: …` | reviewer |
| CHANGES_REQUESTED → READY_FOR_WORKER | "Re-open" button (attempt++) | operator |
| APPROVED → IN_PATCH | "Add to patch" | auditor / operator |
| IN_PATCH → SHIPPED | "Ship patch" (requires `AUDIT_<PATCH>.md DECISION: SHIP`) | operator |
| SHIPPED → ARCHIVED | auto, N days (default 14) | control plane |
| any → CANCELLED | "Cancel" w/ reason | operator |

**State machine rules:**
- No skipping. Can't SHIP without APPROVED+IN_PATCH.
- No dual-claim. OS-level rename collision blocks second worker.
- One in-flight run per task (launch disabled while RUNNING).
- Rework is attempt-numbered; reviewer notes append to HANDOFF rather than overwrite.
- BLOCKED is terminal until operator "Unblock" with reason.
- Every transition writes a row to `task_events (task_id, from_state, to_state, trigger, actor, ts, artifact_path)`.
- Removed: fuzzy `PROVISIONAL_REVIEW`, `AWAITING_WORKER` substates.

---

## 4. Role boundaries + permissions

| Role | Who | Reads | Writes | Cannot |
|---|---|---|---|---|
| Operator | human | everything | `04_DRAFTS\`, control-plane buttons | run worker/reviewer manually (must go through dispatcher) |
| Manager | Sonnet / Opus | `04_DRAFTS`, `09_SHARED_CONTEXT`, source tree | `05_INBOX\HANDOFF+TASK` | touch `06/07/08/10/99`; edit source |
| Worker | Haiku | claimed HANDOFF + its `allowed_files` | `06_OUTBOX\RESULT`, files inside `allowed_files` | read outside `allowed_files`; edit `do_not_touch`; write outside `06` |
| Reviewer | Sonnet | HANDOFF + RESULT + changed files | `07_REVIEWS\REVIEW` | edit source; run mutating shell commands |
| Auditor | Opus | all APPROVED reviews in patch, source diffs | `08_PATCHES\<PATCH>\AUDIT` | override reviewer silently (must cite) |
| Dispatcher | control plane | everything (read) | all folders per writer contract; `CLAUDE_TASK_BOARD.md`; `task_events` | bypass the state machine |

Enforced via `can(role, action, target)` gate in `routes/*`. Violation → 403 + event log.

---

## 5. Artifact schema

**`HANDOFF_<TID>.md`** (authoritative human-readable brief):
```
<!-- writer: manager, task_id: <TID>, patch_id: <PID|pending>, written_at: <iso>, attempt: <n> -->
# <title>
TRACK: A|B
PRIORITY: CRITICAL|HIGH|MEDIUM|LOW
SUBSYSTEM: <tag>
## Objective
## Allowed files
## Do not touch
## Acceptance criteria
## Verification
## Rollback
## Restart required: yes|no
```

**`TASK_<TID>.json`** (machine mirror; must match HANDOFF; control plane owns):
```json
{
  "task_id", "title", "track", "priority", "subsystem",
  "allowed_files": [], "do_not_touch": [],
  "acceptance_criteria": [], "verification": [],
  "rollback": "", "restart_required": false,
  "attempt": 1, "patch_id": "PID|null",
  "status": "READY_FOR_WORKER"
}
```

**`RESULT_<TID>.json`**:
```json
{
  "task_id", "status": "ok|blocked|fail",
  "files_read": [], "files_changed": [],
  "summary": "", "commands_run": [], "tests_run": [],
  "acceptance_criteria_met": {},
  "risks": [], "restart_required": false
}
```

**`REVIEW_<TID>.md`** — first line MUST be `DECISION: APPROVED|CHANGES_REQUESTED|BLOCKED`.

**`AUDIT_<PATCH>.md`** — lives under `08_PATCHES\<PATCH>\`; first line `DECISION: SHIP|BLOCK`.

`bridge/parsers.py` is the single validator. Mismatches → `99_QUARANTINE\` with reason; operator alerted on board.

---

## 6. Patch grouping

```
08_PATCHES\
├── PATCH_PENDING\             alias for the open patch
├── PATCH_2026-04-18-V1\
│   ├── manifest.json          { patch_id, title, created_ts, tasks: [TID…], status: SHIPPED|PENDING, shipped_ts }
│   ├── AUDIT_PATCH_2026-04-18-V1.md
│   └── tasks\                 read-only frozen copies of HANDOFF+RESULT+REVIEW at ship time
```

Rules:
- Exactly one `PATCH_PENDING` at a time.
- APPROVED task → operator clicks "Add to patch" → TID appended to `manifest.json.tasks`.
- Shipping freezes the patch: copies approved artifacts to `tasks\`, sets `shipped_ts`, auto-creates a new `PATCH_PENDING`.
- Source BOT_BRIDGE artifacts stay in place post-ship (for worker context continuity), tagged `shipped_in: PID` in the DB. Archive rotation moves them to `10_ARCHIVE\` after N days.

---

## 7. Control plane wiring + color-coded board

**Code changes (all inside `mlbbot\control_plane\`):**

1. `config.py` — add `BRIDGE_ROOT`, `BOT_SOURCE_ROOT`, `LEGACY_CUTOFF_TS`, `ARCHIVE_AFTER_DAYS` constants.
2. `bridge/parsers.py` — writer-attribution header parsing; per-folder writer validation.
3. `bridge/importer.py` — rogue-file → `99_QUARANTINE`; legacy-tree cutoff assertion; writes `task_events` rows on transitions.
4. `workflow.py` — collapse states to the 10 above; compute `attempt`, `age_bucket` (new | active | stale).
5. `routes/actions.py` — `can(role, action, target)` gate; every mutation writes a `task_events` row.
6. `routes/patches.py` — enforce single PENDING; ship freezes artifacts into `PATCH_<id>\tasks\`.
7. `routes/startup_check.py` (**new**) — runs guardrails 1–5 from §2; `/system` shows pass/fail badges.
8. New DB: tables `task_events`, `quarantined_artifacts`; columns `tasks.attempt`, `tasks.age_first_seen`, `tasks.last_transition_ts`.

**Color-coded board** — each card uses four independent visual signals:

| Signal | Encoding | Values |
|---|---|---|
| **State** | card background hue | READY=blue, CLAIMED=teal, RUNNING=amber-pulse, AWAITING_REVIEW=violet, APPROVED=green, CHANGES_REQUESTED=orange, BLOCKED=red, IN_PATCH=gold, SHIPPED=grey, ARCHIVED=faded |
| **Track / category** | left stripe | Track A (plumbing) = cyan; Track B (alpha) = magenta; subsystem as text label below title |
| **Age + attempt** | top-right badge | NEW (≤ 2h) = bright dot; active (2h–2d) = none; stale (> 2d same state) = yellow warning dot; rework (attempt > 1) = striped border + attempt # |
| **Priority** | left border thickness | CRITICAL thick → LOW hairline |

Lane order on the board follows the state machine left-to-right; CHANGES_REQUESTED appears as a loop-back lane above READY.

---

## 8. Verification (how we know it works end-to-end)

After implementation, run through this checklist on a clean day's bridge:

1. Start control plane → `/system` shows all 5 guardrail badges green.
2. Create task via "New Task" form → `HANDOFF_<TID>.md` + `TASK_<TID>.json` appear in `05_INBOX\`; `task_events` row `∅→DRAFT→READY_FOR_WORKER` present; board card is blue with correct stripe/badge/priority.
3. Drop a mis-named file into `06_OUTBOX\` (e.g. `FOOBAR.md`) → next import moves it to `99_QUARANTINE\` with reason; operator sees banner.
4. Run worker on a real task; confirm card transitions RUNNING (amber-pulse) → AWAITING_REVIEW (violet) as artifacts arrive.
5. Reviewer writes `DECISION: CHANGES_REQUESTED` → card turns orange, gets attempt-2 striped border; re-open button puts it back in READY_FOR_WORKER with attempt=2.
6. Approve two tasks, add both to patch, write `AUDIT_<PATCH>.md DECISION: SHIP`, click ship → `PATCH_<id>\tasks\` populated with frozen copies; new `PATCH_PENDING` auto-created; both cards turn grey (SHIPPED).
7. Touch a file in `Desktop\BOT_BRIDGE\` → restart control plane → startup refuses with cutoff violation message.
8. Simulate two workers claiming the same HANDOFF → second rename fails; board shows collision event.

If all 8 pass, the system is "working properly and finally."

---

## 9. Out of scope for this spec

- Agent personality / gamified hover flavor (already a separate future enhancement per `project_mlbbot_control_plane.md` memory).
- Full MLB model Phase 2/3 integration (separate spec under `project_mlb_model.md`).
- March Madness bot parity (sibling bot, separate spec when needed).
- Replacing the dispatcher or CLI adapter — reuse as-is, only add the state-machine gate.
