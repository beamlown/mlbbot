"""Flask app factory.

Mounts all routes, initializes DB, imports BOT_BRIDGE on startup. Any request
can force a re-import via POST /api/import.
"""
from __future__ import annotations

from pathlib import Path

from flask import Flask, g, render_template

from .config import SETTINGS
from .db import init_db, get_conn
from .bridge.importer import import_bot_bridge
from .startup_check import enforce_on_boot
from .routes.tasks import bp as tasks_bp
from .routes.artifacts import bp as artifacts_bp
from .routes.system import bp as system_bp
from .routes.actions import bp as actions_bp
from .routes.runs import bp as runs_bp
from .routes.patches import bp as patches_bp
from .roles import ROLE_INFO
from .workflow import WORKFLOW_LANES, LANE_DISPLAY


def create_app() -> Flask:
    pkg_dir = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(pkg_dir / "templates"),
        static_folder=str(pkg_dir / "static"),
    )
    app.config["SETTINGS"] = SETTINGS

    # Run anti-drift guardrails before touching the DB or the bridge.
    # Any FAIL aborts boot unless CONTROL_PLANE_FORCE_START=1 is set.
    enforce_on_boot()

    # Bootstrap DB + import BOT_BRIDGE once at process start.
    with app.app_context():
        init_db()
        # Index every file across mlbbot + sibling project roots so the
        # prompt builder can resolve bare filenames to canonical absolute
        # paths. Without this, agents Glob/Grep sibling vs nested vs
        # old-copy candidates and waste turns on the wrong tree.
        try:
            from .file_index import reindex as _reindex_files
            _fi = _reindex_files()
            app.logger.info("file_index: %s", _fi)
        except Exception as e:
            app.logger.warning("file_index.reindex failed: %r", e)
        report = import_bot_bridge()
        app.logger.info(
            "import_bot_bridge: tasks_seen=%d tasks_new=%d artifacts=%d errors=%d",
            report.tasks_seen, report.tasks_new,
            report.artifacts_new, len(report.errors or []),
        )
        # Log the resolved claude binary so the operator can see at startup
        # whether the CLI adapter is going to work without visiting /system.
        from .runner.bin_resolver import resolve_current
        _r = resolve_current()
        if _r.path:
            app.logger.info("claude_bin: resolved=%s (source=%s)", _r.path, _r.source)
        else:
            app.logger.warning(
                "claude_bin: NOT FOUND — claude_cli adapter will fail. "
                "Set the path at /system or CONTROL_PLANE_CLAUDE_BIN=..."
            )

    # Make role list and settings available to every template.
    @app.context_processor
    def _ctx() -> dict:
        conn = get_conn()
        acting = conn.execute(
            "SELECT value FROM settings WHERE key='acting_role'"
        ).fetchone()
        acting_role = (acting["value"] if acting else SETTINGS.default_role)
        counts = {
            r["status"]: r["n"]
            for r in conn.execute(
                "SELECT status, COUNT(*) AS n FROM tasks GROUP BY status"
            ).fetchall()
        }
        # Cheap health probe (no subprocess) so the top bar can warn when
        # the claude binary can't be found.
        from .runner.bin_resolver import resolve_current
        resolved = resolve_current()
        claude_status = {
            "resolved_path": resolved.path or "",
            "ok": bool(resolved.path),
            "source": resolved.source,
        }
        # Release banner context: show the current pending patch (if any)
        # plus the last shipped version. We only read here — we do NOT
        # auto-create a pending patch on every page render; creation
        # happens lazily when the /patches page is visited or when a
        # task is actually approved.
        pending_patch_banner = None
        try:
            _pending_row = conn.execute(
                "SELECT * FROM patches WHERE status='PENDING' "
                "ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            _last_shipped = conn.execute(
                "SELECT version, shipped_at FROM patches WHERE status='SHIPPED' "
                "ORDER BY shipped_at DESC LIMIT 1"
            ).fetchone()
            if _pending_row is not None:
                _pending_count = conn.execute(
                    "SELECT COUNT(*) AS n FROM tasks WHERE patch_id=?",
                    (_pending_row["patch_id"],),
                ).fetchone()["n"]
                pending_patch_banner = {
                    "patch_id": _pending_row["patch_id"],
                    "version": _pending_row["version"],
                    "task_count": _pending_count,
                    "last_shipped_version": _last_shipped["version"] if _last_shipped else None,
                    "last_shipped_at":      _last_shipped["shipped_at"] if _last_shipped else None,
                }
            elif _last_shipped is not None:
                pending_patch_banner = {
                    "patch_id": None,
                    "version": "v(next)",
                    "task_count": 0,
                    "last_shipped_version": _last_shipped["version"],
                    "last_shipped_at":      _last_shipped["shipped_at"],
                }
        except Exception:
            pending_patch_banner = None
        # Dugout OS scoreboard summary — per-lane counts + guardrail fail count.
        from .workflow import bucket as _bucket
        all_tasks = [dict(r) for r in conn.execute("SELECT * FROM tasks").fetchall()]
        bucketed = _bucket(all_tasks)
        lane_counts = {lane: len(rows) for lane, rows in bucketed.items()}
        try:
            from .startup_check import run_all as _run_guardrails
            results = _run_guardrails()
            guardrail_fails = sum(1 for r in results if not r.ok)
        except Exception:
            guardrail_fails = 0
        from .stats import persona_stats as _ps
        roster_rows = conn.execute(
            "SELECT * FROM agent_profiles "
            "WHERE status='ACTIVE' AND enabled=1 "
            "ORDER BY jersey_number"
        ).fetchall()
        roster_stats = {r["profile_id"]: _ps(r["profile_id"]) for r in roster_rows}
        return {
            "ROLE_INFO": ROLE_INFO,
            "ACTING_ROLE": acting_role,
            "TASK_COUNTS": counts,
            "SETTINGS": SETTINGS,
            "WORKFLOW_LANES": WORKFLOW_LANES,
            "LANE_DISPLAY": LANE_DISPLAY,
            "CLAUDE_STATUS": claude_status,
            "PENDING_PATCH": pending_patch_banner,
            "LANE_COUNTS": lane_counts,
            "GUARDRAIL_FAILS": guardrail_fails,
            "ROSTER": [dict(r) for r in roster_rows],
            "ROSTER_STATS": roster_stats,
        }

    app.register_blueprint(tasks_bp)
    app.register_blueprint(artifacts_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(actions_bp)
    app.register_blueprint(runs_bp)
    app.register_blueprint(patches_bp)

    @app.errorhandler(404)
    def _404(e):
        return render_template("404.html", path=str(e)), 404

    return app


# WSGI entrypoint
app = create_app()
