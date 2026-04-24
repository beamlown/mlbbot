"""Run-centric routes: launch, status, SSE stream, cancel, agent list.

All mutations flow through `runner.dispatcher.DISPATCHER`. SSE connections
subscribe to a per-run queue and relay log events to the browser.
"""
from __future__ import annotations

import json
import queue
import secrets
import time
from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify, request, stream_with_context

from ..db import get_conn
from ..roles import ROLE_INFO, can
from ..runner import get_adapter
from ..runner.base import RunRequest
from ..runner.dispatcher import DISPATCHER, END_SENTINEL
from ..runner.capture import finalize_run
from ..workflow import derive_state
from ..bridge.exporter import export_task


bp = Blueprint("runs", __name__)


# Wire up dispatcher callbacks once at import.
DISPATCHER.set_finalize(finalize_run)

# Startup reaper: any `runs` row still marked `running` whose PID is no
# longer alive is a crash-orphan — mark it failed so the board doesn't
# show ghost running tasks across server restarts.
try:
    import logging
    _reaped = DISPATCHER.reap_zombies()
    logging.getLogger(__name__).info("startup reaper: swept %d zombies", _reaped)
except Exception:
    # Never fail module import because the reaper hiccupped.
    pass

# Resume any in-progress patch reviews orphaned by a prior crash. MUST
# run AFTER reap_zombies so any 'running' run rows have been flipped
# first — resume_in_progress checks active dispatcher state, not the DB,
# when deciding whether to relaunch.
try:
    from ..runner.patch_review import resume_in_progress as _resume_prs
    _resumed = _resume_prs()
    if _resumed:
        import logging
        logging.getLogger(__name__).info(
            "startup patch-review resume: relaunched %d orphaned reviews", _resumed,
        )
except Exception:
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _acting_role() -> str:
    row = get_conn().execute(
        "SELECT value FROM settings WHERE key='acting_role'"
    ).fetchone()
    return row["value"] if row else "SONNET_MANAGER"


def _new_run_id() -> str:
    return "RUN_" + secrets.token_hex(6).upper()


def _task_row(task_id: str) -> dict | None:
    row = get_conn().execute(
        "SELECT * FROM tasks WHERE task_id=?", (task_id.upper(),)
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    # Decode allowed/forbidden for prompt building.
    for key in ("allowed_files", "forbidden_files"):
        try:
            d[key] = json.loads(d.get(key) or "[]")
        except Exception:
            d[key] = []
    d["workflow_state"] = derive_state(d)
    return d


def _agent_profile(profile_id: str) -> dict | None:
    row = get_conn().execute(
        "SELECT * FROM agent_profiles WHERE profile_id=?", (profile_id,),
    ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Agent listing
# ---------------------------------------------------------------------------

@bp.route("/api/agents", methods=["GET"])
def api_agents():
    rows = get_conn().execute(
        "SELECT * FROM agent_profiles WHERE enabled=1 ORDER BY created_at"
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["allowed_states"] = json.loads(d.get("allowed_states") or "[]")
        except Exception:
            d["allowed_states"] = []
        out.append(d)
    return jsonify(out)


# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------

@bp.route("/api/tasks/<task_id>/launch", methods=["POST"])
def api_launch(task_id: str):
    body = request.get_json(silent=True) or {}
    profile_id = (body.get("profile_id") or "").strip()
    adapter_name = (body.get("adapter") or "").strip() or None
    extra_prompt = (body.get("extra_prompt") or "").strip() or None
    force = bool(body.get("force"))

    acting = _acting_role()
    if not can(acting, "launch_run"):
        return jsonify({"ok": False, "error": "permission_denied",
                        "detail": f"Role {acting} cannot launch runs."}), 403

    task = _task_row(task_id)
    if task is None:
        return jsonify({"ok": False, "error": "task_not_found"}), 404

    # Block guard: if the task is parked or has a known block reason,
    # refuse to launch unless the operator explicitly overrides with
    # force=true. This is the "don't blindly retry" signal — prevents
    # re-running a task whose prior failure the operator hasn't yet
    # addressed.
    if not force and (task.get("blocked_on") or task.get("block_reason")):
        return jsonify({
            "ok": False, "error": "task_blocked",
            "detail": (task.get("block_reason") or
                       f"parked behind {task.get('blocked_on')}"),
            "blocked_on": task.get("blocked_on"),
            "block_reason": task.get("block_reason"),
            "blocked_at": task.get("blocked_at"),
        }), 409

    # Resolve agent profile.
    if not profile_id:
        return jsonify({"ok": False, "error": "profile_id_required"}), 400
    profile = _agent_profile(profile_id)
    if profile is None or not profile.get("enabled", 1):
        return jsonify({"ok": False, "error": "unknown_profile"}), 404
    try:
        allowed_states = json.loads(profile.get("allowed_states") or "[]")
    except Exception:
        allowed_states = []

    if not force and task["workflow_state"] not in allowed_states:
        return jsonify({
            "ok": False, "error": "task_not_eligible",
            "detail": f"{profile['display']} accepts {allowed_states}, task is {task['workflow_state']}.",
            "task_state": task["workflow_state"],
            "allowed_states": allowed_states,
        }), 409

    role = profile["role"]
    adapter_name = adapter_name or profile.get("adapter") or "claude_cli"
    try:
        adapter = get_adapter(adapter_name)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    run_id = _new_run_id()
    req = RunRequest(
        run_id=run_id,
        task_id=task["task_id"],
        role=role,
        adapter=adapter_name,
        task=task,
        created_by=acting,
        extra_prompt=extra_prompt or profile.get("prompt_extra"),
    )
    prompt_text = adapter.build_prompt(req)
    argv = adapter.build_argv(req, prompt_text)

    # If the adapter offers structured-stream translation (e.g. stream-json
    # events → human lines), hand it to the dispatcher so run_logs + SSE
    # + the on-disk transcript all see the readable form.
    stdout_transform = getattr(adapter, "transform_stdout_line", None)
    row = DISPATCHER.launch(req, argv, prompt_text,
                            stdout_transform=stdout_transform)

    # Two distinct failure paths land as status=failed with a structured
    # prefix in result_summary:
    #   cap_hit:    family concurrency cap reached → 429 (retryable)
    #   spawn_error / other → 500 (likely misconfiguration)
    if (row or {}).get("status") == "failed":
        summary = (row.get("result_summary") or "")
        if summary.startswith("cap_hit:"):
            return jsonify({
                "ok": False, "error": "cap_hit",
                "detail": summary[:500],
                "run": row, "adapter": adapter_name,
            }), 429
        return jsonify({
            "ok": False, "error": "spawn_failed",
            "detail": summary[:500],
            "run": row, "adapter": adapter_name,
        }), 500

    # Stamp the task as assigned to the run's role and mark ACTIVE so the
    # board snaps to the RUNNING lane immediately.
    get_conn().execute(
        "UPDATE tasks SET assigned_role=?, status=?, updated_at=? WHERE task_id=?",
        (role, "ACTIVE", _now_iso(), task["task_id"]),
    )
    try:
        export_task(task["task_id"])
    except Exception:
        pass

    return jsonify({"ok": True, "run": row, "profile_id": profile_id,
                    "role": role, "adapter": adapter_name})


# ---------------------------------------------------------------------------
# Status / history
# ---------------------------------------------------------------------------

@bp.route("/api/runs/<run_id>", methods=["GET"])
def api_run(run_id: str):
    row = get_conn().execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if row is None:
        return jsonify({"ok": False, "error": "not_found"}), 404
    return jsonify({"ok": True, "run": dict(row), "active": DISPATCHER.is_active(run_id)})


@bp.route("/api/runs/<run_id>/logs", methods=["GET"])
def api_run_logs(run_id: str):
    after = int(request.args.get("after") or 0)
    rows = get_conn().execute(
        "SELECT id, ts, stream, line FROM run_logs WHERE run_id=? AND id>? ORDER BY id ASC LIMIT 2000",
        (run_id, after),
    ).fetchall()
    return jsonify({"ok": True, "logs": [dict(r) for r in rows],
                    "active": DISPATCHER.is_active(run_id)})


@bp.route("/api/runs/<run_id>/cancel", methods=["POST"])
def api_run_cancel(run_id: str):
    ok = DISPATCHER.cancel(run_id)
    return jsonify({"ok": ok})


@bp.route("/api/tasks/<task_id>/runs", methods=["GET"])
def api_task_runs(task_id: str):
    rows = get_conn().execute(
        "SELECT * FROM runs WHERE task_id=? ORDER BY created_at DESC LIMIT 50",
        (task_id.upper(),),
    ).fetchall()
    return jsonify({"ok": True, "runs": [dict(r) for r in rows]})


# ---------------------------------------------------------------------------
# SSE
# ---------------------------------------------------------------------------

@bp.route("/api/runs/<run_id>/stream", methods=["GET"])
def api_run_stream(run_id: str):
    """Stream run events as Server-Sent Events.

    Sends a one-shot `history` event with any log rows already persisted,
    then live events from the dispatcher. Closes when the run ends.
    """
    def _format(ev_name: str, data: dict) -> str:
        return f"event: {ev_name}\ndata: {json.dumps(data)}\n\n"

    @stream_with_context
    def gen():
        # Initial status.
        row = get_conn().execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            yield _format("error", {"error": "not_found"})
            return
        yield _format("status", dict(row))

        # History dump.
        hist = get_conn().execute(
            "SELECT id, ts, stream, line FROM run_logs WHERE run_id=? ORDER BY id ASC",
            (run_id,),
        ).fetchall()
        for r in hist:
            yield _format("log", dict(r))

        if not DISPATCHER.is_active(run_id):
            yield _format("end", {"run_id": run_id})
            return

        q = DISPATCHER.subscribe(run_id)
        try:
            last_ping = time.time()
            while True:
                try:
                    ev = q.get(timeout=15)
                except queue.Empty:
                    # SSE keep-alive comment to prevent proxies from closing.
                    yield ": keepalive\n\n"
                    if time.time() - last_ping > 120:
                        break
                    continue
                if ev is END_SENTINEL:
                    break
                yield _format("log", {
                    "ts": ev.ts, "stream": ev.stream, "line": ev.line,
                })
                last_ping = time.time()
        finally:
            DISPATCHER.unsubscribe(run_id, q)

        final = get_conn().execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        yield _format("status", dict(final) if final else {"run_id": run_id})
        yield _format("end", {"run_id": run_id})

    resp = Response(gen(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp
