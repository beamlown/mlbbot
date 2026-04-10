from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

RESTART_DELAY_SECONDS = 5
POLL_INTERVAL_SECONDS = 10

SPORTS_BOT_DIR = Path(__file__).resolve().parent
LAUNCHER_PID_FILE = SPORTS_BOT_DIR / "runtime" / "launcher.pid"
MLB_MODEL_DIR = SPORTS_BOT_DIR.parent / "mlb_model"
LOG_DIR = SPORTS_BOT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

PROCESSES = [
    {
        "name": "shadow_engine",
        "command": [sys.executable, "-m", "integration.recommendation_api"],
        "cwd": str(MLB_MODEL_DIR),
        "log_file": str(LOG_DIR / "shadow_engine.log"),
    },
    {
        "name": "bot_core",
        "command": [sys.executable, "bot_core.py"],
        "cwd": str(SPORTS_BOT_DIR),
        "log_file": str(LOG_DIR / "bot_core_launcher.log"),
    },
    {
        "name": "dashboard",
        "command": [sys.executable, "dashboard_server.py"],
        "cwd": str(SPORTS_BOT_DIR),
        "log_file": str(LOG_DIR / "dashboard.log"),
    },
    {
        "name": "resolution_watcher",
        "command": [sys.executable, "-m", "integration.resolution_watcher"],
        "cwd": str(MLB_MODEL_DIR),
        "log_file": str(LOG_DIR / "resolution_watcher.log"),
    },
]


def start_process(spec: dict, attempt: int = 1) -> tuple[subprocess.Popen, object]:
    log_fh = open(spec["log_file"], "a", encoding="utf-8")
    proc = subprocess.Popen(
        spec["command"],
        cwd=spec["cwd"],
        stdout=log_fh,
        stderr=log_fh,
    )
    print(f"LAUNCHER: {spec['name']} started (pid={proc.pid}, attempt={attempt})", flush=True)
    return proc, log_fh


def stop_process(entry: dict) -> None:
    proc = entry.get("proc")
    fh = entry.get("fh")
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    if fh and not fh.closed:
        fh.close()


def _pid_is_running(pid: int) -> bool:
    """Windows-reliable process liveness check via OpenProcess."""
    PROCESS_QUERY_INFORMATION = 0x0400
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
    if not handle:
        return False
    ctypes.windll.kernel32.CloseHandle(handle)
    return True


def main() -> None:
    if LAUNCHER_PID_FILE.exists():
        try:
            old_pid = int(LAUNCHER_PID_FILE.read_text(encoding="utf-8").strip())
            if _pid_is_running(old_pid):
                print(f"ERROR: launcher already running at PID {old_pid}. Stop it first.", flush=True)
                sys.exit(1)
        except ValueError:
            pass
    LAUNCHER_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAUNCHER_PID_FILE.write_text(str(os.getpid()), encoding="utf-8")

    managed: dict[str, dict] = {}
    for spec in PROCESSES:
        proc, fh = start_process(spec, attempt=1)
        managed[spec["name"]] = {"spec": spec, "proc": proc, "fh": fh, "attempt": 1}

    def _shutdown(*_args):
        print("LAUNCHER: shutting down...", flush=True)
        for entry in managed.values():
            stop_process(entry)
        print("LAUNCHER: all processes terminated.", flush=True)
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    try:
        while True:
            time.sleep(POLL_INTERVAL_SECONDS)
            for name, entry in managed.items():
                rc = entry["proc"].poll()
                if rc is None:
                    continue
                if entry["fh"] and not entry["fh"].closed:
                    entry["fh"].close()
                print(
                    f"LAUNCHER: {name} exited (code={rc}) — restarting in {RESTART_DELAY_SECONDS}s",
                    flush=True,
                )
                time.sleep(RESTART_DELAY_SECONDS)
                entry["attempt"] += 1
                entry["proc"], entry["fh"] = start_process(entry["spec"], attempt=entry["attempt"])
                print(f"LAUNCHER: {name} restarted (attempt {entry['attempt']})", flush=True)
    except KeyboardInterrupt:
        _shutdown()
    finally:
        LAUNCHER_PID_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
