"""Hall of Fame page."""
from __future__ import annotations
from flask import Blueprint, render_template, redirect, url_for

from dugout_dash import hof_sql

bp = Blueprint("hof", __name__)


@bp.route("/hof")
def index():
    return render_template(
        "hof.html",
        ACTIVE="hof",
        BATTING_AVG=hof_sql.batting_avg(),
        SLUGGING=hof_sql.slugging(),
        ERA=hof_sql.era(),
        MVP_DAY=hof_sql.mvp_day(),
        NO_HITTER=hof_sql.no_hitter(),
        TEAM_RECORDS=hof_sql.team_records(),
        DYNASTY=hof_sql.dynasty(),
        ROOKIE=hof_sql.rookie_of_the_year(),
    )


@bp.route("/hof/refresh")
def refresh():
    hof_sql.reset_cache()
    return redirect(url_for("hof.index"))
