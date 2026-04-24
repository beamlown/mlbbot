"""TAPE page — NYSE-style marquee + position-focused wide rows with sparklines."""
from __future__ import annotations
from flask import Blueprint, render_template

from dugout_dash.positions import fetch_open_positions

bp = Blueprint("tape", __name__)


@bp.route("/tape")
def index():
    open_ps = fetch_open_positions()
    try:
        from core.state_hub import GLOBAL_STATE_HUB
        snap = GLOBAL_STATE_HUB.snapshot()
    except Exception:
        snap = {}
    cells = [
        {
            "slug": slug,
            "mark": row.get("current_price"),
            "stale": row.get("stale", False),
        }
        for slug, row in snap.items()
    ]
    return render_template(
        "tape.html",
        ACTIVE="tape",
        CELLS=cells,
        OPEN_POSITIONS=open_ps,
        OPEN_COUNT=len(open_ps),
    )
