"""Echo adapter — no-op runner for tests and local smoke.

Prints the constructed prompt line-by-line with small delays so the SSE
pipeline can be exercised without spending tokens, then emits a final
`RESULT_JSON:` block so the result capture path also gets exercised.
"""
from __future__ import annotations

import json

from .base import Adapter, RunRequest
from .prompts import build_prompt


class EchoAdapter:
    name = "echo"

    def build_prompt(self, req: RunRequest) -> str:
        return build_prompt(req)

    def build_argv(self, req: RunRequest, prompt_text: str) -> list[str]:
        # A tiny Python one-liner. We deliberately use python3 here instead
        # of a shell pipeline — makes it portable and avoids shell escaping
        # pain with the prompt body.
        body = prompt_text.replace("\r", "")
        result = {
            "status": "ok",
            "summary": f"echo run for task {req.task_id or '(none)'} as {req.role}",
            "adapter": self.name,
            "role": req.role,
        }
        script = (
            "import sys, time, json\n"
            "lines = sys.argv[1].splitlines()\n"
            "for ln in lines:\n"
            "    print(ln, flush=True)\n"
            "    time.sleep(0.05)\n"
            "print('--- end of echoed prompt ---', flush=True)\n"
            "print('RESULT_JSON: ' + sys.argv[2], flush=True)\n"
        )
        return ["python3", "-c", script, body, json.dumps(result)]
