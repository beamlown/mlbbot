"""Local `claude` CLI adapter.

Launches the Claude Code CLI with `claude -p "<prompt>" --model <id>` in
non-interactive mode. Relies on the operator already being logged in
(`claude login`) — we deliberately do NOT handle credentials here.
"""
from __future__ import annotations

from ..config import SETTINGS
from ..roles import ROLE_INFO
from .base import Adapter, RunRequest
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
        # `--print` = non-interactive; `--output-format=text` keeps stdout
        # flat so our line pump can stream it. No session resume — every
        # run is fresh.
        return [
            SETTINGS.claude_bin,
            "--print",
            "--output-format", "text",
            "--model", model,
            prompt_text,
        ]
