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
from ..file_index import resolve_task_files


def _layout_block() -> list[str]:
    """Workspace grounding — tells the agent exactly where to look.

    This is a multi-repo workspace: the control plane + BOT_BRIDGE live
    inside mlbbot, but the actual bot runtime + ML model are SIBLING
    directories under Desktop. Agents were wandering because the
    previous block suggested everything lived under mlbbot/. The task's
    `allowed_files` column already carries absolute paths (mostly) — the
    rule is "open what's in allowed_files, do not search for it."

    The text below is intentionally emphatic about not searching because
    every run_log that crashes out to stderr begins with a Glob or Grep
    against the wrong root.
    """
    repo = str(SETTINGS.repo_root)
    parent = str(SETTINGS.repo_root.parent)
    return [
        "WORKSPACE LAYOUT — this is a multi-repo workspace. Read carefully.",
        "",
        f"Working directory (cwd):  {repo}",
        f"  This is the CONTROL PLANE + BOT_BRIDGE host. The actual bot",
        f"  runtime and ML model are SIBLING directories under",
        f"  {parent}, not subfolders of the cwd.",
        "",
        "Project roots in this workspace (all absolute):",
        f"  {repo}",
        f"    contains: control_plane/ (this process), BOT_BRIDGE/ (task",
        f"              inbox + outbox + reviews), run artifacts.",
        f"  {parent}\\sports_bot_v2",
        f"    live bot runtime. bot_core.py, core/, dashboard_server.py,",
        f"    paper_exec.py all live here — NOT under mlbbot.",
        f"  {parent}\\mlb_model",
        f"    calibrated MLB win-probability model. integration/,",
        f"    recommendation_api.py, execution_guard.py.",
        f"  {parent}\\march_madness_bot",
        f"    sibling bot (separate project).",
        "",
        "Authoritative paths:",
        f"  HANDOFFs:   {repo}\\BOT_BRIDGE\\05_INBOX_FROM_MANAGER\\",
        f"  RESULTs:    {repo}\\BOT_BRIDGE\\06_OUTBOX_FROM_WORKER\\",
        f"  Reviews:    {repo}\\BOT_BRIDGE\\07_REVIEWS\\",
        f"  Shared:     {repo}\\BOT_BRIDGE\\08_SHARED_CONTEXT\\",
        f"  There is an older {parent}\\BOT_BRIDGE (no mlbbot prefix) —",
        f"  ignore it. Only the path above is live.",
        "",
        "HARD RULES — your tools will waste turns if you ignore these:",
        "  1. The `allowed_files` section below contains ABSOLUTE paths.",
        "     Open them directly with Read. Do NOT Glob, Grep, or Bash-find",
        "     to locate a file that's already listed.",
        "  2. If a HANDOFF mentions a bare filename (e.g. `bot_core.py`),",
        "     find it in `allowed_files` below. If it's not in",
        "     `allowed_files`, it is out of scope for this task.",
        "  3. Do NOT search Desktop\\sports_bot_v2 and Desktop\\mlbbot",
        "     interchangeably. Each file has exactly one canonical location;",
        "     `allowed_files` gives it to you.",
    ]


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
    # Stubs — patch-review and triage prompts are built by the dedicated
    # builders below (orchestrator bypasses build_prompt entirely).
    "OPUS_PATCH_REVIEWER": "You are the PATCH REVIEWER. (See step/synthesis prompt.)",
    "SONNET_TRIAGE":       "You are TRIAGE. (See triage prompt.)",
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

    # Resolve every allowed_files entry against the on-disk file index so
    # the prompt gives canonical absolute paths, not ambiguous bare names.
    # Entries that don't exist or have multiple candidates are surfaced
    # explicitly — an ambiguous path is information, not a silent fail.
    allowed_resolved  = resolve_task_files(allowed)
    forbidden_resolved = resolve_task_files(forbidden)

    lines = [
        framing,
        "",
        *_layout_block(),
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
        f"Allowed files ({len(allowed)}) — open these directly, do not search:",
    ]
    if not allowed_resolved:
        lines.append("  (none specified)")
    else:
        for entry in allowed_resolved:
            status = entry["status"]
            if status == "ok":
                lines.append(f"  - {entry['resolved'][0]}")
                if entry.get("note"):
                    lines.append(f"      note: {entry['note']} (given: {entry['given']})")
            elif status == "ambiguous":
                lines.append(f"  - {entry['given']}  (AMBIGUOUS — multiple matches):")
                for p in entry["resolved"]:
                    lines.append(f"      * {p}")
                lines.append("      Pick the one that fits the task subsystem; do NOT")
                lines.append("      Glob/Grep to decide — ask the operator if unsure.")
            else:  # missing
                lines.append(f"  - {entry['given']}  (NOT FOUND in indexed roots — stop and")
                lines.append("      emit status='blocked' if this file is load-bearing)")
    if forbidden_resolved:
        lines += ["", f"Forbidden files ({len(forbidden)}) — do NOT touch:"]
        for entry in forbidden_resolved:
            if entry["resolved"]:
                for p in entry["resolved"]:
                    lines.append(f"  - {p}")
            else:
                lines.append(f"  - {entry['given']}")
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


# ---------------------------------------------------------------------------
# Patch-review + triage prompt builders.
#
# These are called directly by runner/patch_review.py (the orchestrator)
# and by the Sonnet-triage hook in runner/capture.py. They bypass the
# role-dispatched build_prompt() because they need inputs that RunRequest
# doesn't carry (patch metadata, prior-step TL;DRs, aggregated summaries).
# ---------------------------------------------------------------------------


def build_sonnet_triage_prompt(task: dict, result_json_text: str) -> str:
    """2-line yes/no: does RESULT.summary satisfy HANDOFF.acceptance?

    Contract: the model's final stdout line MUST start with `TRIAGE: yes`
    or `TRIAGE: no — <short reason>`. capture.py greps for that anchor to
    set task status (DONE on yes, CHANGES_REQUESTED + block_reason on no).
    """
    tid = task.get("task_id") or "(no-task)"
    title = task.get("title") or ""
    acceptance = (task.get("acceptance") or "(see HANDOFF)").strip()
    allowed = task.get("allowed_files") or []
    if isinstance(allowed, str):
        try: allowed = json.loads(allowed)
        except Exception: allowed = []
    lines = [
        "You are the TRIAGE gate. You look at ONE worker RESULT and answer ONE question:",
        "does the RESULT plausibly satisfy the task's acceptance criteria?",
        "",
        *_layout_block(),
        "",
        f"Task: {tid} — {title}",
        "",
        "Acceptance:",
        acceptance,
        "",
        f"Allowed files ({len(allowed)}):",
        *[f"  - {a}" for a in (allowed or ['(none)'])],
        "",
        "RESULT (verbatim):",
        "-" * 70,
        (result_json_text or "(missing)").strip(),
        "-" * 70,
        "",
        "Judge only against the acceptance criteria. If RESULT.status is not",
        "'ok', answer no. If summary/files_changed don't plausibly match the",
        "acceptance ask, answer no. Otherwise answer yes.",
        "",
        "Your final stdout line MUST be exactly one of:",
        "  TRIAGE: yes",
        "  TRIAGE: no — <one-sentence reason, <=120 chars>",
        "",
        "Do not write any file. Do not edit any file. Use Read only if needed.",
    ]
    return "\n".join(lines)


def build_patch_review_step_prompt(
    *,
    patch: dict,
    task: dict,
    handoff_text: str,
    result_json_text: str,
    prior_summaries: list[str],
    step_index: int,
    total_steps: int,
) -> str:
    """Per-task step of a sequential patch review.

    Writes BOT_BRIDGE/07_REVIEWS/PATCH_<pid>/REVIEW_<task>.md. Response
    body MUST end with a `TL;DR:` line followed by exactly 5 single-line
    bullet points — the orchestrator greps for that anchor and carries
    the bullets forward into the next step's `prior_summaries`.
    """
    pid = patch.get("patch_id") or "(no-patch)"
    version = patch.get("version") or "(no-version)"
    tid = task.get("task_id") or "(no-task)"
    title = task.get("title") or ""
    review_dir = f"BOT_BRIDGE/07_REVIEWS/PATCH_{pid}"
    review_file = f"{review_dir}/REVIEW_{tid}.md"

    prior_block = []
    if prior_summaries:
        prior_block = ["Prior-step TL;DRs (in order):", ""]
        for i, s in enumerate(prior_summaries, start=1):
            prior_block.append(f"Step {i}:")
            prior_block.append(s.rstrip())
            prior_block.append("")

    lines = [
        "You are the PATCH REVIEWER. You are reviewing one task at a time",
        "within a larger patch. After every task step, the orchestrator",
        "extracts your TL;DR and carries it into the next step so you can",
        "flag cross-task drift. A final synthesis step will render the",
        "overall ship verdict.",
        "",
        *_layout_block(),
        "",
        f"Patch: {pid} (version {version})",
        f"Step: {step_index + 1} of {total_steps}",
        f"Task: {tid} — {title}",
        "",
        *prior_block,
        "=" * 70,
        f"HANDOFF — {tid}",
        "=" * 70,
        (handoff_text or "(missing)").rstrip(),
        "=" * 70,
        "",
        "=" * 70,
        f"RESULT — {tid}",
        "=" * 70,
        (result_json_text or "(missing)").strip(),
        "=" * 70,
        "",
        "Your job:",
        f"  1. Verify the RESULT satisfies the HANDOFF acceptance.",
        f"  2. Check the code on disk — the allowed_files listed in the task.",
        f"     Do NOT modify any file; this is a read-only review.",
        f"  3. Flag any drift from prior steps' TL;DRs.",
        f"  4. Write your review to: {review_file}",
        f"     (create the directory {review_dir} if it doesn't exist)",
        f"  5. The review body MUST end with the literal anchor line `TL;DR:`",
        f"     followed by exactly 5 single-line bullet points. No extra text",
        f"     after the 5th bullet.",
        "",
        "Decision line inside the review: one of",
        "  DECISION: APPROVED",
        "  DECISION: CHANGES_REQUESTED — <one-line reason>",
        "  DECISION: FAIL — <one-line reason>",
        "",
        "Example ending of your review file:",
        "  DECISION: APPROVED",
        "  ",
        "  TL;DR:",
        "  - files_changed matched allowed_files exactly",
        "  - acceptance criteria satisfied as written",
        "  - no regression risk observed in neighboring code",
        "  - consistent with prior-step conclusions",
        "  - ready to ship as part of patch " + pid,
    ]
    return "\n".join(lines)


def build_patch_synthesis_prompt(
    *,
    patch: dict,
    summaries: list[str],
    failed_steps: list[dict],
    tasks: list[dict],
) -> str:
    """Final step: render PATCH_REVIEW_<pid>.md with overall decision.

    Reads all TL;DRs + any skipped/failed step notes and emits one
    ship/changes/fail verdict. Response body writes to disk.
    """
    pid = patch.get("patch_id") or "(no-patch)"
    version = patch.get("version") or "(no-version)"
    review_dir = f"BOT_BRIDGE/07_REVIEWS/PATCH_{pid}"
    review_file = f"{review_dir}/PATCH_REVIEW_{pid}.md"

    summary_block = []
    for i, s in enumerate(summaries, start=1):
        t = tasks[i - 1] if i - 1 < len(tasks) else {}
        summary_block.append(f"### Step {i} — {t.get('task_id','?')} · {t.get('title','')}")
        summary_block.append(s.rstrip())
        summary_block.append("")

    failed_block = []
    if failed_steps:
        failed_block = ["## Steps that failed to complete", ""]
        for fs in failed_steps:
            failed_block.append(
                f"- Step {fs.get('index','?')} ({fs.get('task_id','?')}): "
                f"{fs.get('reason','(no reason)')}"
            )
        failed_block.append("")

    lines = [
        "You are the PATCH REVIEWER — SYNTHESIS step. Every per-task step of",
        "this patch has been completed; you now read the TL;DRs and render",
        "the single ship verdict for the entire patch.",
        "",
        *_layout_block(),
        "",
        f"Patch: {pid} (version {version})",
        f"Total tasks reviewed: {len(summaries)}",
        f"Failed/skipped steps: {len(failed_steps)}",
        "",
        "## Per-step TL;DRs",
        "",
        *summary_block,
        *failed_block,
        "Your job:",
        f"  1. Synthesize the per-step TL;DRs into one ship verdict.",
        f"  2. Flag any cross-task concerns (e.g. task B touched files that",
        f"     task A also changed, or two tasks make contradictory claims).",
        f"  3. Write the final review to: {review_file}",
        f"  4. End with one decision line: one of",
        "       DECISION: SHIP",
        "       DECISION: CHANGES_REQUESTED — <one-line reason>",
        "       DECISION: BLOCK — <one-line reason>",
        "",
        "Keep the file under ~200 lines. It is the operator-facing",
        "ship-or-don't-ship document for the whole patch.",
    ]
    return "\n".join(lines)
