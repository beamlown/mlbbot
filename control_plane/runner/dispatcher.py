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

import json
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
from ..roles import ROLE_INFO
from .base import LogEvent, RunRequest, passthrough_transform


# Sentinel pushed into subscriber queues when the run is finished.
_END_SENTINEL = object()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pid_alive(pid: int | None) -> bool:
    """Return True iff a process with this PID is currently alive.

    Used by the startup reaper to tell a truly-running row from a
    crash-orphaned one. The parent dispatcher that recorded the row
    is gone (this process is a fresh start), so we can't inspect a
    Popen — we have to ask the OS.
    """
    if not pid or pid <= 0:
        return False
    import sys
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
        except Exception:
            return True  # can't check → assume alive (safer than false-reap)
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        k = ctypes.windll.kernel32
        h = k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not h:
            return False
        try:
            code = wintypes.DWORD()
            ok = k.GetExitCodeProcess(h, ctypes.byref(code))
            if not ok:
                return False
            return code.value == STILL_ACTIVE
        finally:
            k.CloseHandle(h)
    else:
        try:
            os.kill(int(pid), 0)
            return True
        except (ProcessLookupError, OSError):
            return False


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
    # Transform each raw stdout line into zero-or-more display lines.
    # stderr is always passthrough (plain-text warnings from the child).
    stdout_transform: Callable[[str], list[str]] = passthrough_transform


class RunDispatcher:
    """Singleton-per-process dispatcher. Holds live Popens + SSE subscribers."""

    LAST_LINES_BUFFER = 400
    # Per-family concurrency caps. Each claude subprocess holds ~300–500 MB
    # of RAM, so the limits are RAM-first rather than CPU-first. One slow
    # Opus review must not starve three Haiku workers; the caps are per
    # family so fan-out is fair across model tiers. Overrides:
    #   CONTROL_PLANE_CAP_OPUS, _SONNET, _HAIKU
    FAMILY_CAPS: dict[str, int] = {
        "opus":   int(os.environ.get("CONTROL_PLANE_CAP_OPUS",   "1")),
        "sonnet": int(os.environ.get("CONTROL_PLANE_CAP_SONNET", "2")),
        "haiku":  int(os.environ.get("CONTROL_PLANE_CAP_HAIKU",  "3")),
    }

    def __init__(self) -> None:
        self._runs: dict[str, _ActiveRun] = {}
        self._lock = threading.RLock()
        self._finalize_cb: Callable[[_ActiveRun, int], None] | None = None

    def active_count(self) -> int:
        with self._lock:
            return len(self._runs)

    def active_by_family(self) -> dict[str, int]:
        """Count currently-running subprocesses grouped by model family."""
        counts: dict[str, int] = {f: 0 for f in self.FAMILY_CAPS}
        with self._lock:
            for run in self._runs.values():
                info = ROLE_INFO.get(run.request.role)
                fam = info.family if info else None
                if fam in counts:
                    counts[fam] += 1
        return counts

    def reap_zombies(self) -> int:
        """Clean up runs whose PID is gone but whose DB row still says running.

        Called once at startup: when the server crashed or was restarted
        while a subprocess was live, the waiter thread never finalized the
        row. Without sweeping, those rows accumulate and the board shows
        ghost "running" tasks forever.
        """
        conn = get_conn()
        rows = conn.execute(
            "SELECT run_id, pid FROM runs WHERE status='running'"
        ).fetchall()
        reaped = 0
        now = _now_iso()
        for r in rows:
            pid = r["pid"] if hasattr(r, "keys") else r[1]
            rid = r["run_id"] if hasattr(r, "keys") else r[0]
            if _pid_alive(pid):
                continue
            conn.execute(
                "UPDATE runs SET status='failed', finished_at=?, exit_code=-1, "
                "result_summary=? WHERE run_id=? AND status='running'",
                (now, "reaper: pid gone", rid),
            )
            conn.execute(
                "INSERT INTO run_logs(run_id, ts, stream, line) VALUES (?,?,?,?)",
                (rid, now, "meta", f"reaper: pid {pid} gone at startup"),
            )
            reaped += 1
        return reaped

    # ------------------------------------------------------------------ lifecycle

    def set_finalize(self, cb: Callable[[_ActiveRun, int], None]) -> None:
        """Install the post-exit hook (usually `capture.finalize_run`)."""
        self._finalize_cb = cb

    # ------------------------------------------------------------------ launch

    def launch(self, req: RunRequest, argv: list[str], prompt_text: str,
               cwd: Path | None = None,
               stdout_transform: Callable[[str], list[str]] | None = None) -> dict:
        """Start the subprocess and the pump threads. Returns DB row dict."""
        conn = get_conn()
        now = _now_iso()
        runs_dir = SETTINGS.runs_dir
        runs_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = runs_dir / f"{req.run_id}.stdout.log"
        stderr_path = runs_dir / f"{req.run_id}.stderr.log"

        # Per-family concurrency cap. Record the run row so the UI can still
        # show it in history, then mark it failed with a structured prefix
        # (`cap_hit:`) that routes/runs.py turns into a 429 response.
        info = ROLE_INFO.get(req.role)
        family = info.family if info else None
        cap = self.FAMILY_CAPS.get(family, 0) if family else 0
        with self._lock:
            active_family = sum(
                1 for r in self._runs.values()
                if ROLE_INFO.get(r.request.role)
                and ROLE_INFO[r.request.role].family == family
            ) if family else 0
        pr_meta = json.dumps(req.patch_review_meta) if req.patch_review_meta else None
        if family and active_family >= cap:
            msg = (f"cap_hit: family={family} active={active_family} cap={cap} "
                   f"(override with CONTROL_PLANE_CAP_{family.upper()})")
            conn.execute(
                """INSERT INTO runs
                   (run_id, task_id, role, adapter, status, cmdline, prompt_text,
                    stdout_path, stderr_path, created_at, created_by,
                    finished_at, exit_code, result_summary, patch_review_meta)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (req.run_id, req.task_id, req.role, req.adapter, "failed",
                 " ".join(_shell_repr(a) for a in argv), prompt_text,
                 str(stdout_path), str(stderr_path), now, req.created_by,
                 now, -1, msg[:500], pr_meta),
            )
            conn.execute(
                "INSERT INTO run_logs(run_id, ts, stream, line) VALUES (?,?,?,?)",
                (req.run_id, now, "meta", msg),
            )
            return self._row(req.run_id)

        conn.execute(
            """INSERT INTO runs
               (run_id, task_id, role, adapter, status, cmdline, prompt_text,
                stdout_path, stderr_path, created_at, created_by,
                patch_review_meta)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                req.run_id, req.task_id, req.role, req.adapter, "queued",
                " ".join(_shell_repr(a) for a in argv),
                prompt_text,
                str(stdout_path), str(stderr_path),
                now, req.created_by,
                pr_meta,
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
                stdin=subprocess.PIPE,
                text=True,
                # Force UTF-8 on every stream. The Windows default for
                # subprocess.Popen(text=True) is locale.getencoding() →
                # cp1252, which chokes on HANDOFF bodies containing
                # em-dashes, arrows, or any other non-Latin-1 content
                # the moment we write the prompt to stdin. Disk writes
                # elsewhere in the control plane already use UTF-8; this
                # makes the subprocess boundary consistent.
                encoding="utf-8",
                errors="replace",
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

        # Deliver the prompt via stdin. Windows cmd.exe caps argv at 8191
        # chars; once the HANDOFF body is inlined, a positional prompt
        # truncates and the child receives only the role framing. stdin
        # has no such limit. We write from a daemon thread so a very large
        # prompt hitting a full pipe buffer never stalls this launch path.
        def _feed_stdin(p: subprocess.Popen, text: str, run_id: str) -> None:
            try:
                if p.stdin is not None:
                    p.stdin.write(text)
            except Exception as e:
                self._emit(run_id, "meta", f"[stdin-write-error] {e!r}")
            finally:
                try:
                    if p.stdin is not None:
                        p.stdin.close()
                except Exception:
                    pass
        threading.Thread(
            target=_feed_stdin, args=(popen, prompt_text, req.run_id),
            daemon=True, name=f"stdin-{req.run_id}",
        ).start()

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
            stdout_transform=stdout_transform or passthrough_transform,
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
        # stdout goes through the adapter's transformer (e.g. JSON events →
        # human lines). stderr is always passthrough — it's plain text from
        # the child and must never be fed to a JSON parser.
        transform = run.stdout_transform if stream == "stdout" else passthrough_transform
        try:
            with disk.open("a", encoding="utf-8") as fh:
                for raw in pipe:
                    line = raw.rstrip("\r\n")
                    try:
                        display_lines = transform(line)
                    except Exception as e:
                        display_lines = [line, f"[transform-error] {e!r}"]
                    for out in display_lines:
                        fh.write(out + "\n")
                        fh.flush()
                        self._emit(run.run_id, stream, out)
                        if stream == "stdout":
                            with run.lock:
                                run.last_lines.append(out)
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

        # Drop the active row BEFORE handing off to the finalize callback.
        # The finalize hook often chains the next run (patch-review
        # orchestrator, triage launcher) and the family cap check must
        # see this finishing run as free, not still-running. Holding a
        # local `run` reference keeps the object alive for the callback.
        with self._lock:
            subs = list(run.subscribers)
            self._runs.pop(run.run_id, None)

        # Hand off to the capture step (safe: runs in this thread).
        if self._finalize_cb is not None:
            try:
                self._finalize_cb(run, exit_code)
            except Exception as e:
                self._emit(run.run_id, "meta", f"[finalize-error] {e!r}")
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
