"""Background subprocess dispatcher.

One thread per run: spawns `subprocess.Popen`, pumps stdout + stderr line
by line into `run_logs`, fans each line out to any SSE subscribers, and
on exit hands off to `capture.finalize_run()` for artifact + transition
handling.

The DB connection from `db.get_conn()` is thread-safe because we open it
with `check_same_thread=False` + WAL + autocommit. SQLite serializes
writes internally.
"""
from __future__ import annotations

import os
import queue
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from ..config import SETTINGS
from ..db import get_conn
from .base import LogEvent, RunRequest


# Sentinel pushed into subscriber queues when the run is finished.
_END_SENTINEL = object()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class _ActiveRun:
    run_id: str
    request: RunRequest
    popen: subprocess.Popen
    threads: list[threading.Thread]
    subscribers: list[queue.Queue]
    stdout_path: Path
    stderr_path: Path
    started_at: str
    last_lines: list[str]        # rolling buffer (last N stdout lines) for result parsing
    lock: threading.Lock


class RunDispatcher:
    """Singleton-per-process dispatcher. Holds live Popens + SSE subscribers."""

    LAST_LINES_BUFFER = 400

    def __init__(self) -> None:
        self._runs: dict[str, _ActiveRun] = {}
        self._lock = threading.RLock()
        self._finalize_cb: Callable[[_ActiveRun, int], None] | None = None

    # ------------------------------------------------------------------ lifecycle

    def set_finalize(self, cb: Callable[[_ActiveRun, int], None]) -> None:
        """Install the post-exit hook (usually `capture.finalize_run`)."""
        self._finalize_cb = cb

    # ------------------------------------------------------------------ launch

    def launch(self, req: RunRequest, argv: list[str], prompt_text: str,
               cwd: Path | None = None) -> dict:
        """Start the subprocess and the pump threads. Returns DB row dict."""
        conn = get_conn()
        now = _now_iso()
        runs_dir = SETTINGS.runs_dir
        runs_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = runs_dir / f"{req.run_id}.stdout.log"
        stderr_path = runs_dir / f"{req.run_id}.stderr.log"

        conn.execute(
            """INSERT INTO runs
               (run_id, task_id, role, adapter, status, cmdline, prompt_text,
                stdout_path, stderr_path, created_at, created_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                req.run_id, req.task_id, req.role, req.adapter, "queued",
                " ".join(_shell_repr(a) for a in argv),
                prompt_text,
                str(stdout_path), str(stderr_path),
                now, req.created_by,
            ),
        )

        # Open subprocess. We deliberately do not set a shell; argv is a list.
        env = dict(os.environ)
        # Make sure stdout is unbuffered line-by-line in the child.
        env.setdefault("PYTHONUNBUFFERED", "1")
        try:
            popen = subprocess.Popen(
                argv,
                cwd=str(cwd or SETTINGS.repo_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,       # line-buffered
                env=env,
            )
        except (FileNotFoundError, OSError, PermissionError) as e:
            msg = f"spawn_error: {e.__class__.__name__}: {e}"
            hint = (
                f"  argv[0] = {argv[0]!r}\n"
                f"  cwd     = {cwd or SETTINGS.repo_root}\n"
                f"  hint    = is the binary on PATH? set CONTROL_PLANE_CLAUDE_BIN "
                f"to the absolute path, or use adapter=echo for a smoke test."
            )
            now = _now_iso()
            conn.execute(
                "UPDATE runs SET status='failed', finished_at=?, exit_code=?, result_summary=? WHERE run_id=?",
                (now, -1, msg[:500], req.run_id),
            )
            # Persist a readable log so /api/runs/<id>/logs and the SSE
            # history dump surface the real error instead of an empty pane.
            conn.execute(
                "INSERT INTO run_logs(run_id, ts, stream, line) VALUES (?,?,?,?)",
                (req.run_id, now, "stderr", msg),
            )
            conn.execute(
                "INSERT INTO run_logs(run_id, ts, stream, line) VALUES (?,?,?,?)",
                (req.run_id, now, "meta", hint),
            )
            return self._row(req.run_id)

        started_at = _now_iso()
        conn.execute(
            "UPDATE runs SET status='running', pid=?, started_at=? WHERE run_id=?",
            (popen.pid, started_at, req.run_id),
        )
        self._emit(req.run_id, "meta", f"▶ launched pid={popen.pid} adapter={req.adapter}")

        active = _ActiveRun(
            run_id=req.run_id,
            request=req,
            popen=popen,
            threads=[],
            subscribers=[],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            started_at=started_at,
            last_lines=[],
            lock=threading.Lock(),
        )

        t_out = threading.Thread(target=self._pump, args=(active, "stdout"), daemon=True)
        t_err = threading.Thread(target=self._pump, args=(active, "stderr"), daemon=True)
        t_wait = threading.Thread(target=self._waiter, args=(active,), daemon=True)
        active.threads = [t_out, t_err, t_wait]

        with self._lock:
            self._runs[req.run_id] = active
        t_out.start()
        t_err.start()
        t_wait.start()

        return self._row(req.run_id)

    # ------------------------------------------------------------------ subscribers

    def subscribe(self, run_id: str) -> queue.Queue:
        """Return a queue that receives new LogEvents; EOF is a sentinel."""
        q: queue.Queue = queue.Queue(maxsize=1000)
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                # Already finished — feed history and close.
                q.put(_END_SENTINEL)
                return q
            run.subscribers.append(q)
        return q

    def unsubscribe(self, run_id: str, q: queue.Queue) -> None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return
            try:
                run.subscribers.remove(q)
            except ValueError:
                pass

    def is_active(self, run_id: str) -> bool:
        with self._lock:
            return run_id in self._runs

    def cancel(self, run_id: str) -> bool:
        with self._lock:
            run = self._runs.get(run_id)
        if run is None:
            return False
        try:
            run.popen.terminate()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------ internals

    def _row(self, run_id: str) -> dict:
        row = get_conn().execute(
            "SELECT * FROM runs WHERE run_id=?", (run_id,),
        ).fetchone()
        return dict(row) if row else {"run_id": run_id}

    def _emit(self, run_id: str, stream: str, line: str) -> None:
        ts = _now_iso()
        get_conn().execute(
            "INSERT INTO run_logs(run_id, ts, stream, line) VALUES (?,?,?,?)",
            (run_id, ts, stream, line),
        )
        ev = LogEvent(ts=ts, stream=stream, line=line)
        with self._lock:
            run = self._runs.get(run_id)
            subs = list(run.subscribers) if run else []
        for q in subs:
            try:
                q.put_nowait(ev)
            except queue.Full:
                pass  # drop slow subscriber's tail

    def _pump(self, run: _ActiveRun, stream: str) -> None:
        pipe = run.popen.stdout if stream == "stdout" else run.popen.stderr
        disk = run.stdout_path if stream == "stdout" else run.stderr_path
        if pipe is None:
            return
        try:
            with disk.open("a", encoding="utf-8") as fh:
                for raw in pipe:
                    line = raw.rstrip("\r\n")
                    fh.write(line + "\n")
                    fh.flush()
                    self._emit(run.run_id, stream, line)
                    if stream == "stdout":
                        with run.lock:
                            run.last_lines.append(line)
                            if len(run.last_lines) > self.LAST_LINES_BUFFER:
                                del run.last_lines[: len(run.last_lines) - self.LAST_LINES_BUFFER]
        except Exception as e:
            self._emit(run.run_id, "meta", f"[pump-{stream}-error] {e!r}")

    def _waiter(self, run: _ActiveRun) -> None:
        exit_code = run.popen.wait()
        # Drain pumps
        for t in run.threads:
            if t is not threading.current_thread():
                t.join(timeout=2.0)

        finished_at = _now_iso()
        status = "succeeded" if exit_code == 0 else "failed"
        get_conn().execute(
            "UPDATE runs SET status=?, exit_code=?, finished_at=? WHERE run_id=?",
            (status, exit_code, finished_at, run.run_id),
        )
        self._emit(run.run_id, "meta", f"■ exit={exit_code} status={status}")

        # Hand off to the capture step (safe: runs in this thread).
        if self._finalize_cb is not None:
            try:
                self._finalize_cb(run, exit_code)
            except Exception as e:
                self._emit(run.run_id, "meta", f"[finalize-error] {e!r}")

        # Notify SSE subscribers and drop the active row.
        with self._lock:
            subs = list(run.subscribers)
            self._runs.pop(run.run_id, None)
        for q in subs:
            try:
                q.put_nowait(_END_SENTINEL)
            except queue.Full:
                pass


def _shell_repr(arg: str) -> str:
    """Quote an argv element for display only — never fed back to a shell."""
    if any(ch in arg for ch in " \t\n\"'\\$`"):
        return '"' + arg.replace('"', '\\"')[:200] + ('"' if len(arg) <= 200 else '…"')
    return arg


# Module-level singleton.
DISPATCHER = RunDispatcher()
END_SENTINEL = _END_SENTINEL
