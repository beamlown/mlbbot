"""Role + permission model.

Phase 1 ships the definitions; enforcement is wired in Phase 4. Import-safe.
"""
from __future__ import annotations

from dataclasses import dataclass


ROLES = (
    "OPUS_ARCHITECT",
    "OPUS_AUDITOR",
    "OPUS_REVIEWER",
    "SONNET_MANAGER",
    "SONNET_WORKER",
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
    "OPUS_ARCHITECT": RoleInfo("OPUS_ARCHITECT", "Opus · Architect",  "opus",   "architect"),
    "OPUS_AUDITOR":   RoleInfo("OPUS_AUDITOR",   "Opus · Auditor",    "opus",   "auditor"),
    "OPUS_REVIEWER":  RoleInfo("OPUS_REVIEWER",  "Opus · Reviewer",   "opus",   "reviewer"),
    "SONNET_MANAGER": RoleInfo("SONNET_MANAGER", "Sonnet · Manager",  "sonnet", "manager"),
    "SONNET_WORKER":  RoleInfo("SONNET_WORKER",  "Sonnet · Worker",   "sonnet", "worker"),
    "HAIKU_WORKER":   RoleInfo("HAIKU_WORKER",   "Haiku · Worker",    "haiku",  "worker"),
}


def can(role: str, capability: str) -> bool:
    return CAPABILITIES.get(role, {}).get(capability, False)
