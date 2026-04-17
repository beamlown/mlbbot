"""Local `claude` CLI adapter.

Launches the Claude Code CLI with `claude --print --output-format text
--model <id> "<prompt>"` in non-interactive mode. Relies on the operator
already being logged in (`claude login`) — we deliberately do NOT handle
credentials here.

Binary discovery goes through `bin_resolver.resolve_current()` so Windows
users don't have to set an env var; the /system page lets them override
the path from the UI.
"""
from __future__ import annotations

from ..roles import ROLE_INFO
from .base import Adapter, RunRequest
from .bin_resolver import resolve_current, wrap_for_platform
from .prompts import build_prompt


# Role-family → Claude model id
_FAMILY_MODEL = {
    "opus":   "claude-opus-4-7",
    "sonnet": "claude-sonnet-4-6",
    "haiku":  "claude-haiku-4-5-20251001",
}


class ClaudeCliAdapter:
    name = "claude_cli"

    def build_prompt(self, req: RunRequest) -> str:
        return build_prompt(req)

    def build_argv(self, req: RunRequest, prompt_text: str) -> list[str]:
        info = ROLE_INFO.get(req.role)
        model = _FAMILY_MODEL.get(info.family if info else "", "claude-sonnet-4-6")

        resolved = resolve_current()
        # If resolution failed, still emit a sentinel argv so the dispatcher's
        # spawn-error path produces a useful log line pointing at /system.
        binpath = resolved.path or "claude"

        # `--permission-mode bypassPermissions` is required for --print mode
        # to actually use tools: without it, the non-interactive child can't
        # prompt the operator for approval and returns a plain-text "please
        # enable permissions" message instead of doing the work.
        args = [
            "--print",
            "--permission-mode", "bypassPermissions",
            "--output-format", "text",
            "--model", model,
            prompt_text,
        ]
        return wrap_for_platform(binpath, args)
