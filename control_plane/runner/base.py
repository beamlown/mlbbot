"""Runner protocol + tiny data carriers.

An `Adapter` knows how to turn a role + task into an argv list and a
prompt string. The dispatcher never imports a concrete adapter — it
only sees this interface.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class RunRequest:
    run_id: str
    task_id: str | None
    role: str
    adapter: str
    task: dict | None            # full task row as dict (from `tasks`)
    created_by: str | None       # acting role at launch time
    extra_prompt: str | None = None


@dataclass
class LogEvent:
    ts: str
    stream: str                  # "stdout" | "stderr" | "meta"
    line: str


class Adapter(Protocol):
    name: str

    def build_prompt(self, req: RunRequest) -> str: ...
    def build_argv(self, req: RunRequest, prompt_text: str) -> list[str]: ...
