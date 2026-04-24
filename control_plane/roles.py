"""Role + permission model.

Phase 1 ships the definitions; enforcement is wired in Phase 4. Import-safe.
"""
from __future__ import annotations

from dataclasses import dataclass


ROLES = (
    "OPUS_ARCHITECT",
    "OPUS_AUDITOR",
    "OPUS_REVIEWER",           # retained for history; no new per-task reviews launched
    "OPUS_PATCH_REVIEWER",     # sequential per-task review of a whole patch + synthesis
    "SONNET_MANAGER",
    "SONNET_WORKER",
    "SONNET_TRIAGE",           # 2-line yes/no gate between worker RESULT and patch assignment
    "HAIKU_WORKER",
)


# Capability matrix. True = allowed by default; wired by a Flask before_request
# guard in Phase 4. Comments describe intent.
CAPABILITIES: dict[str, dict[str, bool]] = {
    "OPUS_ARCHITECT": {
        "read_any":            True,
        "create_task":         True,
        "edit_task":           False,
        "transition_task":     False,
        "assign_task":         False,
        "write_spec":          True,
        "write_audit":         True,
        "write_review":        False,
        "write_result":        False,
        "launch_run":          True,
        "mutate_settings":     False,
    },
    "OPUS_AUDITOR": {
        "read_any":            True,
        "create_task":         False,
        "edit_task":           False,
        "transition_task":     False,
        "assign_task":         False,
        "write_spec":          False,
        "write_audit":         True,
        "write_review":        False,
        "write_result":        False,
        "launch_run":          True,
        "mutate_settings":     False,
    },
    "OPUS_REVIEWER": {
        "read_any":            True,
        "create_task":         False,
        "edit_task":           False,
        # Opus reviewer may only transition to DONE after its own APPROVED review.
        "transition_task":     True,
        "assign_task":         False,
        "write_spec":          False,
        "write_audit":         False,
        "write_review":        True,
        "write_result":        False,
        "launch_run":          True,
        "mutate_settings":     False,
        "transition_patch":    False,
    },
    "OPUS_PATCH_REVIEWER": {
        # Sole Opus gate before ship. Reviews the whole patch — one sequential
        # step per task with TL;DRs carried forward, then a synthesis step.
        "read_any":            True,
        "create_task":         False,
        "edit_task":           False,
        "transition_task":     False,
        "assign_task":         False,
        "write_spec":          False,
        "write_audit":         False,
        "write_review":        True,
        "write_result":        False,
        "launch_run":          True,
        "mutate_settings":     False,
        "transition_patch":    True,
    },
    "SONNET_TRIAGE": {
        # Cheap semantic gate between worker RESULT and patch assignment:
        # "does RESULT.summary satisfy HANDOFF.acceptance? yes/no". Auto-
        # launched by the capture hook; never invoked directly by a human.
        "read_any":            True,
        "create_task":         False,
        "edit_task":           False,
        "transition_task":     True,    # flips task DONE on yes, CHANGES_REQUESTED on no
        "assign_task":         False,
        "write_spec":          False,
        "write_audit":         False,
        "write_review":        True,
        "write_result":        False,
        "launch_run":          True,
        "mutate_settings":     False,
        "transition_patch":    False,
    },
    "SONNET_MANAGER": {
        "read_any":            True,
        "create_task":         True,
        "edit_task":           True,
        "transition_task":     True,
        "assign_task":         True,
        "write_spec":          True,
        "write_audit":         True,
        "write_review":        True,
        "write_result":        False,
        "launch_run":          True,
        "mutate_settings":     True,
    },
    "SONNET_WORKER": {
        "read_any":            True,
        "create_task":         False,
        "edit_task":           False,
        "transition_task":     False,
        "assign_task":         False,
        "write_spec":          False,
        "write_audit":         False,
        "write_review":        False,
        "write_result":        True,
        "launch_run":          False,
        "mutate_settings":     False,
    },
    "HAIKU_WORKER": {
        "read_any":            True,
        "create_task":         False,
        "edit_task":           False,
        "transition_task":     False,
        "assign_task":         False,
        "write_spec":          False,
        "write_audit":         False,
        "write_review":        False,
        "write_result":        True,
        "launch_run":          False,   # launched BY a manager, never self-launched
        "mutate_settings":     False,
    },
}


@dataclass(frozen=True)
class RoleInfo:
    name: str
    display: str
    family: str      # opus | sonnet | haiku
    kind: str        # architect | auditor | reviewer | manager | worker


ROLE_INFO: dict[str, RoleInfo] = {
    "OPUS_ARCHITECT":      RoleInfo("OPUS_ARCHITECT",      "Opus · Architect",      "opus",   "architect"),
    "OPUS_AUDITOR":        RoleInfo("OPUS_AUDITOR",        "Opus · Auditor",        "opus",   "auditor"),
    "OPUS_REVIEWER":       RoleInfo("OPUS_REVIEWER",       "Opus · Reviewer",       "opus",   "reviewer"),
    "OPUS_PATCH_REVIEWER": RoleInfo("OPUS_PATCH_REVIEWER", "Opus · Patch Reviewer", "opus",   "patch_reviewer"),
    "SONNET_MANAGER":      RoleInfo("SONNET_MANAGER",      "Sonnet · Manager",      "sonnet", "manager"),
    "SONNET_WORKER":       RoleInfo("SONNET_WORKER",       "Sonnet · Worker",       "sonnet", "worker"),
    "SONNET_TRIAGE":       RoleInfo("SONNET_TRIAGE",       "Sonnet · Triage",       "sonnet", "triage"),
    "HAIKU_WORKER":        RoleInfo("HAIKU_WORKER",        "Haiku · Worker",        "haiku",  "worker"),
}


def can(role: str, capability: str) -> bool:
    return CAPABILITIES.get(role, {}).get(capability, False)
