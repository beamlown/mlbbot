"""Typed dataclasses that mirror BOT_BRIDGE artifact schemas.

Used by parsers and routes so JSON going in and out of the UI stays consistent.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any


VALID_STATUSES = (
    "PENDING", "QUEUED", "ACTIVE", "BLOCKED",
    "DONE", "CHANGES_REQUESTED", "ARCHIVED",
)
VALID_PRIORITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")

# Lanes shown on the board (left to right).
LANES = ("ACTIVE", "QUEUED", "BLOCKED", "CHANGES_REQUESTED", "DONE", "ARCHIVED")


@dataclass
class Task:
    task_id: str
    title: str
    type: str = "unspecified"
    priority: str = "MEDIUM"
    status: str = "PENDING"
    issued: str | None = None
    subsystem: str | None = None
    evidence: str | None = None
    allowed_files: list[str] = field(default_factory=list)
    forbidden_files: list[str] = field(default_factory=list)
    acceptance: str | None = None
    notes: str | None = None
    brief_path: str | None = None
    result_path: str | None = None
    review_path: str | None = None
    assigned_role: str | None = None
    outcome: str | None = None

    @classmethod
    def from_row(cls, row) -> "Task":
        def _loads(s: str | None) -> list[str]:
            if not s:
                return []
            try:
                v = json.loads(s)
                return v if isinstance(v, list) else []
            except Exception:
                return []
        return cls(
            task_id=row["task_id"],
            title=row["title"],
            type=row["type"],
            priority=row["priority"],
            status=row["status"],
            issued=row["issued"],
            subsystem=row["subsystem"],
            evidence=row["evidence"],
            allowed_files=_loads(row["allowed_files"]),
            forbidden_files=_loads(row["forbidden_files"]),
            acceptance=row["acceptance"],
            notes=row["notes"],
            brief_path=row["brief_path"],
            result_path=row["result_path"],
            review_path=row["review_path"],
            assigned_role=row["assigned_role"],
            outcome=row["outcome"],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ArtifactRef:
    artifact_id: str
    kind: str
    path: str
    title: str | None
    mtime: int
    relation: str | None = None


@dataclass
class Run:
    run_id: str
    task_id: str | None
    role: str
    adapter: str
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    result_summary: str | None = None


@dataclass
class Review:
    review_id: str
    task_id: str
    decision: str          # APPROVED | CHANGES_REQUESTED | FAIL | PROVISIONAL
    reviewer: str
    summary: str | None
    created_at: str
