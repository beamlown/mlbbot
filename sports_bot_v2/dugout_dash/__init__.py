"""dugout_dash — Flask app factory."""
from __future__ import annotations
from flask import Flask

from dugout_dash import config as cfg
from dugout_dash.blueprints import game as game_bp
from dugout_dash.blueprints import api as api_bp
from dugout_dash.blueprints import trades as trades_bp
from dugout_dash.blueprints import tape as tape_bp
from dugout_dash.blueprints import system as system_bp
from dugout_dash.blueprints import hof as hof_bp


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["JSON_SORT_KEYS"] = False

    @app.context_processor
    def inject_globals():
        open_count = 0
        today_pnl = 0.0
        bankroll = cfg.STARTING_BANKROLL
        try:
            import sqlite3
            with sqlite3.connect(cfg.DB_PATH, timeout=1.5) as conn:
                open_count = conn.execute(
                    "SELECT COUNT(*) FROM trades WHERE status='open'"
                ).fetchone()[0] or 0
                today_pnl = conn.execute(
                    "SELECT COALESCE(SUM(pnl_usd),0) FROM trades"
                    " WHERE status='closed' AND ts_close >= datetime('now','-1 day')"
                ).fetchone()[0] or 0.0
                realized = conn.execute(
                    "SELECT COALESCE(SUM(pnl_usd),0) FROM trades WHERE status='closed'"
                ).fetchone()[0] or 0.0
                bankroll = cfg.STARTING_BANKROLL + realized
        except Exception:
            pass
        live_count = 0
        try:
            from core import espn_cache
            games = espn_cache.get_scoreboard().get("games", [])
            live_count = sum(1 for g in games if g.get("inning", 0) > 0 and g.get("status") != "STATUS_FINAL")
        except Exception:
            pass
        return {
            "PORT": cfg.PORT,
            "DB_PATH": cfg.DB_PATH,
            "BOT_VERSION": "0.4.2",
            "BANKROLL": float(bankroll),
            "TODAY_PNL": float(today_pnl),
            "LIVE_COUNT": live_count,
            "OPEN_COUNT": open_count,
        }

    app.register_blueprint(game_bp.bp)
    app.register_blueprint(api_bp.bp)
    app.register_blueprint(trades_bp.bp)
    app.register_blueprint(tape_bp.bp)
    app.register_blueprint(system_bp.bp)
    app.register_blueprint(hof_bp.bp)

    if not app.config.get("TESTING"):
        try:
            from dugout_dash.market_tap import GLOBAL_MARKET_TAP
            GLOBAL_MARKET_TAP.start()
        except Exception as e:
            import logging
            logging.getLogger("dugout").warning("market_tap start failed: %s", e)
        try:
            from core import espn_cache
            espn_cache.start()
        except Exception as e:
            import logging
            logging.getLogger("dugout").warning("espn_cache start failed: %s", e)

    @app.route("/healthz")
    def healthz():
        return {"ok": True, "app": "dugout_dash"}

    return app
