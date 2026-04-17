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
from .routes.tasks import bp as tasks_bp
from .routes.artifacts import bp as artifacts_bp
from .routes.system import bp as system_bp
from .routes.actions import bp as actions_bp
from .roles import ROLE_INFO


def create_app() -> Flask:
    pkg_dir = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(pkg_dir / "templates"),
        static_folder=str(pkg_dir / "static"),
    )
    app.config["SETTINGS"] = SETTINGS

    # Bootstrap DB + import BOT_BRIDGE once at process start.
    with app.app_context():
        init_db()
        report = import_bot_bridge()
        app.logger.info(
            "import_bot_bridge: tasks_seen=%d tasks_new=%d artifacts=%d errors=%d",
            report.tasks_seen, report.tasks_new,
            report.artifacts_new, len(report.errors or []),
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
        return {
            "ROLE_INFO": ROLE_INFO,
            "ACTING_ROLE": acting_role,
            "TASK_COUNTS": counts,
            "SETTINGS": SETTINGS,
        }

    app.register_blueprint(tasks_bp)
    app.register_blueprint(artifacts_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(actions_bp)

    @app.errorhandler(404)
    def _404(e):
        return render_template("404.html", path=str(e)), 404

    return app


# WSGI entrypoint
app = create_app()
