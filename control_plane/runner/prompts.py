"""Role-aware prompt templates.

These are intentionally terse. The HANDOFF_*.md file on disk is the
authoritative brief — we just point the run at it and tell the model
what kind of work is expected for the role.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..config import SETTINGS
from ..roles import ROLE_INFO


_ROLE_FRAMING = {
    "OPUS_ARCHITECT": (
        "You are an ARCHITECT. Produce a specification or audit note. Do not "
        "write production code. Output should be saved as a SPEC_*.md or "
        "AUDIT_*.md under BOT_BRIDGE/08_SHARED_CONTEXT/ when complete."
    ),
    "OPUS_AUDITOR": (
        "You are an AUDITOR. Read-only. Produce findings + evidence. Output "
        "as an AUDIT_*.md under BOT_BRIDGE/08_SHARED_CONTEXT/."
    ),
    "OPUS_REVIEWER": (
        "You are a REVIEWER. Inspect the worker's RESULT + evidence. Produce "
        "REVIEW_<TASK>.md under BOT_BRIDGE/07_REVIEWS/ with a clear decision: "
        "APPROVED | CHANGES_REQUESTED | FAIL."
    ),
    "SONNET_MANAGER": (
        "You are the MANAGER. You may edit the task board, issue handoffs, "
        "and transition tasks. Do not execute worker code."
    ),
    "SONNET_WORKER": (
        "You are a WORKER. Read the HANDOFF carefully and produce the "
        "requested change, restricted to the task's `allowed_files`. Do NOT "
        "touch any path in `forbidden_files`. When done, WRITE your result "
        "to BOT_BRIDGE/06_OUTBOX_FROM_WORKER/RESULT_<TASK>.json as a JSON "
        "object containing at minimum {status, summary, files_changed[], "
        "notes?, next_steps?}. `status` must be one of `ok` | `blocked` | "
        "`fail`. This file is the authoritative result — the control plane "
        "reads it directly."
    ),
    "HAIKU_WORKER": (
        "You are a WORKER. Read the HANDOFF carefully and produce the "
        "requested change, restricted to the task's `allowed_files`. Do NOT "
        "touch any path in `forbidden_files`. When done, WRITE your result "
        "to BOT_BRIDGE/06_OUTBOX_FROM_WORKER/RESULT_<TASK>.json as a JSON "
        "object containing at minimum {status, summary, files_changed[], "
        "notes?, next_steps?}. `status` must be one of `ok` | `blocked` | "
        "`fail`. This file is the authoritative result — the control plane "
        "reads it directly."
    ),
}


def build_prompt(req) -> str:
    role = req.role
    framing = _ROLE_FRAMING.get(role, f"Acting as {role}.")
    task = req.task or {}
    tid = task.get("task_id") or req.task_id or "(no-task)"
    title = task.get("title") or ""
    subsystem = task.get("subsystem") or "(unspecified)"
    priority = task.get("priority") or "MEDIUM"
    acceptance = task.get("acceptance") or "(see HANDOFF)"
    brief_rel = task.get("brief_path") or f"05_INBOX_FROM_MANAGER/HANDOFF_{tid}.md"

    allowed = task.get("allowed_files") or []
    forbidden = task.get("forbidden_files") or []
    if isinstance(allowed, str):
        try: allowed = json.loads(allowed)
        except Exception: allowed = []
    if isinstance(forbidden, str):
        try: forbidden = json.loads(forbidden)
        except Exception: forbidden = []

    brief_abs = SETTINGS.bridge_root / Path(brief_rel)
    bridge_rel = str(SETTINGS.bridge_root.relative_to(SETTINGS.repo_root)) \
        if SETTINGS.bridge_root.is_relative_to(SETTINGS.repo_root) else str(SETTINGS.bridge_root)

    # Inline the HANDOFF body directly. Workers previously drifted to
    # unrelated tasks because they were free to read other HANDOFF_*.md
    # files in the same inbox directory. Giving them the exact content
    # here eliminates the need for a directory read entirely.
    try:
        handoff_text = brief_abs.read_text(encoding="utf-8")
    except Exception as e:
        handoff_text = f"(HANDOFF file could not be read: {e})"

    # Ground the model in the repo layout up front. Without this, workers
    # Glob/Grep the entire machine looking for files referenced by name in
    # the HANDOFF. cwd here matches `dispatcher.launch(cwd=SETTINGS.repo_root)`.
    repo_root = str(SETTINGS.repo_root)
    layout_block = [
        f"Working directory: {repo_root}",
        "Do NOT search outside this root. All task paths are relative to it.",
        "",
        "Repo layout (top-level only):",
        "  sports_bot_v2/   — live bot runtime (bot_core.py lives here)",
        "  mlb_model/       — calibrated MLB win-prob model",
        "  BOT_BRIDGE/      — task inbox/outbox, reviews, shared context",
        "  control_plane/   — orchestrator (Flask + SQLite, this process)",
        "",
        "For files in `allowed_files`: open them directly — do not search.",
        "If a HANDOFF mentions a filename without a directory prefix, check",
        "`allowed_files` first; that list is the authoritative location.",
    ]

    lines = [
        framing,
        "",
        *layout_block,
        "",
        f"Role: {ROLE_INFO.get(role).display if role in ROLE_INFO else role}",
        f"Task: {tid} — {title}",
        f"Priority: {priority}",
        f"Subsystem: {subsystem}",
        f"BOT_BRIDGE root: {bridge_rel}",
        "",
        "Acceptance:",
        acceptance,
        "",
        f"Allowed files ({len(allowed)}):",
        *[f"  - {a}" for a in (allowed or ['(none specified)'])],
    ]
    if forbidden:
        lines += ["", f"Forbidden files ({len(forbidden)}):"]
        lines += [f"  - {f}" for f in forbidden]
    if req.extra_prompt:
        lines += ["", "Operator note:", req.extra_prompt]
    role_kind = ROLE_INFO.get(role).kind if role in ROLE_INFO else ""
    if role_kind == "worker":
        lines += [
            "",
            "=" * 70,
            f"HANDOFF — {tid}  (your ONLY task; ignore all others)",
            "=" * 70,
            handoff_text.rstrip(),
            "=" * 70,
            "",
            "ABSOLUTE RULES — obey these before anything else:",
            f"  1. Your task is ONLY {tid}. Do not work on any other task.",
            f"  2. Do NOT read any other HANDOFF_*.md file in 05_INBOX_FROM_MANAGER/.",
            f"     The handoff above is the complete brief. Do not browse the inbox.",
            f"  3. Write your result ONLY to RESULT_{tid}.json — no other filename.",
            f"  4. If another task ID appears in your reasoning, stop and re-read "
            f"the HANDOFF above. You may only produce output for {tid}.",
            f"  5. If you cannot complete {tid} (unclear scope, missing info, "
            f"blocked by something), write RESULT_{tid}.json with "
            f"status='blocked' and explain. Do NOT substitute another task.",
            "",
            f"When done, write your verdict to "
            f"BOT_BRIDGE/06_OUTBOX_FROM_WORKER/RESULT_{tid}.json as a single "
            "JSON object: {status, summary, files_changed[], notes?, "
            "next_steps?}. `status` is one of `ok` | `blocked` | `fail`. "
            "The control plane reads that file as the canonical result — "
            "you do not need to also print RESULT_JSON on stdout.",
        ]
    else:
        lines += [
            "",
            "=" * 70,
            f"HANDOFF — {tid}",
            "=" * 70,
            handoff_text.rstrip(),
            "=" * 70,
            "",
            "When you are done, print a final line prefixed by `RESULT_JSON:` "
            "containing a JSON object with at minimum a `status` field "
            "(`ok` | `blocked` | `fail`) and a `summary` field.",
        ]
    return "\n".join(lines)
