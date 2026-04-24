"""Role-based permission gate for control-plane mutations.

Canonical matrix: who is allowed to do what. Called from routes/actions
(before every write), and from routes/patches (ship_patch / add_to_patch).

Roles (lowercase throughout):
  operator     — the human at the console
  manager      — Sonnet/Opus dispatcher
  worker       — Haiku executor
  reviewer     — Sonnet verifier
  auditor      — Opus patch-level synthesis
  control_plane— the app itself (archive rotation, board regen, etc.)

Actions:
  create_task   — instantiate a new task (DRAFT → READY_FOR_WORKER)
  edit_task     — modify fields on an existing task (before worker claim)
  claim_task    — rename HANDOFF → .claimed
  launch_run    — dispatch a claude CLI subprocess for a task
  write_result  — produce RESULT_<TID>.json in 06_OUTBOX
  write_review  — produce REVIEW_<TID>.md in 07_REVIEWS
  write_audit   — produce AUDIT_<PATCH>.md in 08_PATCHES
  add_to_patch  — bind an APPROVED task to the pending patch
  ship_patch    — freeze the pending patch into SHIPPED
  unblock       — clear BLOCKED with a reason
  cancel        — move any non-SHIPPED task to ARCHIVED
  archive       — auto-rotate SHIPPED tasks to 10_ARCHIVE
  release_persona— move an active persona to RELEASED with a reason
  sign_persona   — create a new ACTIVE persona for a vacant role slot
"""
from __future__ import annotations

from typing import Optional


# Deny-by-default; only the allowed (role, action) pairs return True.
_MATRIX: dict[tuple[str, str], bool] = {
    # operator: almost everything
    ("operator",      "create_task"):   True,
    ("operator",      "edit_task"):     True,
    ("operator",      "launch_run"):    True,
    ("operator",      "add_to_patch"):  True,
    ("operator",      "ship_patch"):    True,
    ("operator",      "unblock"):       True,
    ("operator",      "cancel"):        True,
    ("operator",      "release_persona"): True,
    ("operator",      "sign_persona"):    True,

    # control_plane: system-level actions
    ("control_plane", "create_task"):   True,
    ("control_plane", "edit_task"):     True,
    ("control_plane", "launch_run"):    True,
    ("control_plane", "add_to_patch"):  True,
    ("control_plane", "archive"):       True,

    # manager: author briefs, edit before claim
    ("manager",       "create_task"):   True,
    ("manager",       "edit_task"):     True,

    # worker: claim + write results within its lane
    ("worker",        "claim_task"):    True,
    ("worker",        "write_result"):  True,

    # reviewer: decide the verdict
    ("reviewer",      "write_review"):  True,

    # auditor: patch-level synthesis
    ("auditor",       "write_audit"):   True,
    ("auditor",       "add_to_patch"):  True,
}


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def can(role: str, action: str, target: Optional[str] = None) -> bool:
    """Return True iff `role` is allowed to perform `action` on `target`.

    Target is advisory for now (future: per-patch ACLs, per-task owners).
    """
    r = _norm(role)
    a = _norm(action)
    if not r or not a:
        return False
    return _MATRIX.get((r, a), False)


class PermissionDenied(PermissionError):
    pass


def require(role: str, action: str, target: Optional[str] = None) -> None:
    """Raise PermissionDenied if `role` can't perform `action`.

    Caller should catch this and convert to a 403 in HTTP contexts.
    """
    if not can(role, action, target):
        raise PermissionDenied(
            f"role={role!r} not permitted to perform action={action!r}"
            + (f" on target={target!r}" if target else "")
        )


if __name__ == "__main__":
    # Inline smoke test. Run with: python -m control_plane.permissions
    cases = [
        ("operator", "ship_patch", True),
        ("operator", "write_review", False),   # operator delegates review
        ("worker", "write_result", True),
        ("worker", "write_review", False),     # worker cannot self-approve
        ("reviewer", "write_review", True),
        ("reviewer", "launch_run", False),     # reviewers don't dispatch
        ("auditor", "write_audit", True),
        ("auditor", "ship_patch", False),      # auditor recommends, operator ships
        ("manager", "create_task", True),
        ("manager", "ship_patch", False),
        ("control_plane", "archive", True),
        ("", "create_task", False),
        ("worker", "", False),
        ("ghost", "ship_patch", False),
        ("operator", "release_persona", True),
        ("operator", "sign_persona",    True),
        ("worker",   "release_persona", False),
        ("manager",  "sign_persona",    False),
    ]
    failed = 0
    for role, action, expected in cases:
        got = can(role, action)
        ok = got == expected
        status = "OK " if ok else "FAIL"
        print(f"{status}  can({role!r:18s}, {action!r:14s}) -> {got!s:5}  (expected {expected})")
        if not ok:
            failed += 1
    if failed:
        raise SystemExit(f"{failed} permission smoke tests failed")
    print("all permission smoke tests passed")
