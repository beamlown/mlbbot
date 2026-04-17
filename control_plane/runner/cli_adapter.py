"""Local `claude` CLI adapter.

Launches the Claude Code CLI with `claude --print --output-format
stream-json --verbose --model <id> "<prompt>"` in non-interactive mode.
Relies on the operator already being logged in (`claude login`) — we
deliberately do NOT handle credentials here.

Why stream-json and not text: `--output-format text` only emits the
final assistant message. During tool-use phases (Read/Grep/Bash) stdout
stays empty, so reviewer runs that spend minutes doing tool work show
zero bytes until they finish. stream-json emits one JSON event per
tool call, thinking block, assistant message, and terminal result —
giving the control-plane UI real-time visibility into progress.

Binary discovery goes through `bin_resolver.resolve_current()` so Windows
users don't have to set an env var; the /system page lets them override
the path from the UI.
"""
from __future__ import annotations

import json

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


_SNIPPET_MAX = 200


def _short(s: str, n: int = _SNIPPET_MAX) -> str:
    s = s.replace("\r", " ").replace("\n", " ⏎ ")
    return s if len(s) <= n else s[: n - 1] + "…"


def _tool_brief(name: str, inp: dict) -> str:
    """Render a one-line summary of a tool_use event's most useful field."""
    if not isinstance(inp, dict):
        return _short(str(inp))
    # Heuristic: prefer the most informative field per common tool.
    for key in ("command", "file_path", "path", "pattern", "query", "url",
                "prompt", "description"):
        v = inp.get(key)
        if v:
            return f"{key}={_short(str(v))}"
    # Fallback: any string value.
    for k, v in inp.items():
        if isinstance(v, (str, int, float)):
            return f"{k}={_short(str(v))}"
    return "(no-args)"


def transform_stream_line(raw: str) -> list[str]:
    """Convert one `--output-format stream-json` event into display lines.

    Return value feeds run_logs, SSE subscribers, the on-disk stdout.log,
    and `last_lines` (used by capture.py to parse RESULT_JSON + decision).
    Assistant text blocks are split on newlines so a `RESULT_JSON: {...}`
    line surfaces anchored for the existing regex.
    """
    raw = raw.rstrip()
    if not raw:
        return []
    try:
        ev = json.loads(raw)
    except Exception:
        # Non-JSON stdout (shouldn't happen with --output-format stream-json,
        # but be safe so a weird warning line doesn't get swallowed).
        return [raw]
    et = ev.get("type")
    if et == "system" and ev.get("subtype") == "init":
        sid = (ev.get("session_id") or "")[-8:]
        model = ev.get("model") or ""
        return [f"[session] id={sid} model={model}"]
    if et == "rate_limit_event":
        info = ev.get("rate_limit_info") or {}
        status = info.get("status") or "?"
        if status == "allowed":
            return []  # noisy; suppress the common case
        return [f"[rate-limit] status={status}"]
    if et == "assistant":
        msg = ev.get("message") or {}
        out: list[str] = []
        for block in msg.get("content") or []:
            bt = block.get("type")
            if bt == "thinking":
                t = (block.get("thinking") or "").strip().splitlines()
                head = t[0] if t else ""
                if head:
                    out.append(f"[thinking] {_short(head)}")
            elif bt == "tool_use":
                name = block.get("name", "?")
                brief = _tool_brief(name, block.get("input") or {})
                out.append(f"[tool→ {name}] {brief}")
            elif bt == "text":
                txt = block.get("text") or ""
                # Split so anchored patterns (RESULT_JSON:, APPROVED) match.
                lines = txt.splitlines() or [""]
                out.extend(lines)
        return out
    if et == "user":
        # Tool results come back as a synthetic user turn.
        msg = ev.get("message") or {}
        out = []
        for block in msg.get("content") or []:
            if block.get("type") == "tool_result":
                c = block.get("content")
                if isinstance(c, list):
                    c = "".join(
                        (b.get("text", "") if isinstance(b, dict) else str(b))
                        for b in c
                    )
                c = str(c or "").strip()
                first = c.splitlines()[0] if c else ""
                out.append(f"[tool← {len(c)}B] {_short(first)}")
        return out
    if et == "result":
        err = "ok" if not ev.get("is_error") else f"err({ev.get('api_error_status')})"
        dur = ev.get("duration_ms")
        turns = ev.get("num_turns")
        return [f"[done] {err} duration={dur}ms turns={turns}"]
    # Unknown event — emit a compact tag rather than the full JSON.
    return [f"[{et or 'event'}]"]


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
        # `stream-json` requires `--verbose` when combined with `--print`.
        # Prompt is delivered via stdin (see dispatcher.launch): cmd.exe on
        # Windows caps its command line at 8191 chars, so a positional prompt
        # gets silently truncated once the inlined HANDOFF body pushes past
        # that limit. stdin has no such cap; claude --print reads from it
        # when no positional prompt is given.
        args = [
            "--print",
            "--permission-mode", "bypassPermissions",
            "--output-format", "stream-json",
            "--verbose",
            "--model", model,
        ]
        return wrap_for_platform(binpath, args)

    def transform_stdout_line(self, raw: str) -> list[str]:
        return transform_stream_line(raw)
