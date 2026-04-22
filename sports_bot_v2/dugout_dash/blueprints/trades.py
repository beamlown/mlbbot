"""TRADES page — open positions + closed today."""
from __future__ import annotations
from flask import Blueprint, render_template

from dugout_dash.positions import fetch_open_positions, fetch_closed_today

bp = Blueprint("trades", __name__)


@bp.route("/trades")
def index():
    open_ps = fetch_open_positions()
    closed = fetch_closed_today()
    return render_template(
        "trades.html",
        ACTIVE="trades",
        OPEN_POSITIONS=open_ps,
        CLOSED_TODAY=closed,
        OPEN_COUNT=len(open_ps),
    )
