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

    lines = [
        framing,
        "",
        f"Role: {ROLE_INFO.get(role).display if role in ROLE_INFO else role}",
        f"Task: {tid} — {title}",
        f"Priority: {priority}",
        f"Subsystem: {subsystem}",
        f"BOT_BRIDGE root: {bridge_rel}",
        f"HANDOFF: {brief_rel}  (absolute: {brief_abs})",
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
            "When you are done, print a final line prefixed by `RESULT_JSON:` "
            "containing a JSON object with at minimum a `status` field "
            "(`ok` | `blocked` | `fail`) and a `summary` field.",
        ]
    return "\n".join(lines)
