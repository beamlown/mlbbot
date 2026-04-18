# ROLES — filesystem-as-queue pattern

Three role prompts + three launchers. The control plane Flask server
stays running for the dashboard + the full-patch Opus synthesis button,
but day-to-day work flows through these terminals directly.

## One-time setup

Nothing — the launchers below handle the model pinning.

## Launching

From `mlbbot\`:

```
start-worker.bat        :: opens a Haiku session, worker role
start-reviewer.bat      :: opens a Sonnet session, reviewer role
start-auditor.bat       :: opens an Opus session, auditor role
```

Each launcher opens `claude` with the correct model flag. As the first
prompt of each session, paste the matching `ROLES/*.md` file. From
then on you drive each terminal with one-word commands:

- Worker terminal  → `go`
- Reviewer terminal → `review`
- Auditor terminal  → `audit v0.2.0`

## Semi-auto polling

If you want a terminal to auto-pull work every minute:

```
/loop 60s go
/loop 60s review
```

(Opus audits are patch-scoped so you invoke them manually.)

## Queue mechanics

```
BOT_BRIDGE\05_INBOX_FROM_MANAGER\
  HANDOFF_<TID>.md           — available to claim
  HANDOFF_<TID>.md.claimed   — someone is working on it
  HANDOFF_<TID>.md.done      — work completed; RESULT written
  TASK_<TID>.json            — machine-readable task metadata
```

Claim-to-lock: worker renames `.md` → `.md.claimed` BEFORE reading the
body. Prevents two worker terminals stepping on each other.

## What the control plane still gives you

- Visual board at http://127.0.0.1:8787 (lanes, filters, patch view)
- `/api/patches/<pid>/review` button — fire the Opus patch-synthesis
  when a patch is ready to ship
- File-index DB for "is this filename canonical?" lookups
- Audit trail (run_logs table) if you ever need to diff a run
- Stays running as-is; you do not need to interact with it for worker
  or reviewer cycles to happen.

## What this pattern fixes

The Flask orchestrator was spawning Claude CLI subprocesses with stdin
piping, argv quoting, and Windows encoding that chewed two days of
debugging. This bypasses all of that — the three terminals ARE the
three agents, using their native tool APIs. No stdin, no argv, no
cp1252, no cap race.
