"""Runner subsystem — launches role-aware Claude runs as subprocesses.

Adapters map a (role, task) pair to a concrete argv + prompt. The
`dispatcher.RunDispatcher` takes those and runs them in a background
thread, multiplexing stdout/stderr into `run_logs` + any SSE subscribers.

Adapter registry is explicit — add a new adapter by importing it here
and registering in `ADAPTERS`.
"""
from __future__ import annotations

from .base import Adapter, LogEvent, RunRequest
from .prompts import build_prompt
from .cli_adapter import ClaudeCliAdapter
from .echo_adapter import EchoAdapter


ADAPTERS: dict[str, Adapter] = {
    ClaudeCliAdapter.name: ClaudeCliAdapter(),
    EchoAdapter.name:      EchoAdapter(),
}


def get_adapter(name: str) -> Adapter:
    if name not in ADAPTERS:
        raise ValueError(f"unknown adapter {name!r} — choose from {sorted(ADAPTERS)}")
    return ADAPTERS[name]


__all__ = [
    "Adapter",
    "LogEvent",
    "RunRequest",
    "ADAPTERS",
    "get_adapter",
    "build_prompt",
]
