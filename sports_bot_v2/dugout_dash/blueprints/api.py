"""API blueprint — SSE endpoint + JSON endpoints."""
from __future__ import annotations

import json
import os
import queue
import time

from flask import Blueprint, Response, jsonify, request, stream_with_context

from dugout_dash.events import GLOBAL_EVENT_BUS

bp = Blueprint("api", __name__, url_prefix="/api")

HEARTBEAT_SEC = 15.0
QUEUE_POLL_SEC = 0.5


@bp.route("/events")
def events_stream():
    def gen():
        q = GLOBAL_EVENT_BUS.subscribe()
        try:
            yield _format_sse("hello", {"subscribers": GLOBAL_EVENT_BUS.subscriber_count()})
            last_beat = time.monotonic()
            while True:
                try:
                    frame = q.get(timeout=QUEUE_POLL_SEC)
                    yield _format_sse(frame["type"], frame["payload"])
                except queue.Empty:
                    pass
                now = time.monotonic()
                if now - last_beat > HEARTBEAT_SEC:
                    yield ": ping\n\n"
                    last_beat = now
        finally:
            GLOBAL_EVENT_BUS.unsubscribe(q)

    return Response(
        stream_with_context(gen()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@bp.route("/events/test_publish", methods=["POST"])
def events_test_publish():
    if os.getenv("DUGOUT_DASH_DEV", "0") != "1":
        return {"error": "dev-only"}, 403
    body = request.get_json(force=True, silent=True) or {}
    GLOBAL_EVENT_BUS.publish(body.get("type", "x"), body.get("payload", {}))
    return {"ok": True}


def _format_sse(event_type: str, payload: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"


@bp.route("/trades.json")
def trades_json():
    from dugout_dash.positions import fetch_open_positions, fetch_closed_today
    return jsonify({
        "open": fetch_open_positions(),
        "closed_today": fetch_closed_today(),
    })


@bp.route("/tape.json")
def tape_json():
    """All currently-tracked markets + last mark, for TAPE ticker strip."""
    try:
        from core.state_hub import GLOBAL_STATE_HUB
        snap = GLOBAL_STATE_HUB.snapshot()
    except Exception:
        snap = {}
    cells = []
    for slug, row in snap.items():
        cells.append({
            "slug": slug,
            "mark": row.get("current_price"),
            "best_bid": row.get("best_bid"),
            "best_ask": row.get("best_ask"),
            "stale": row.get("stale", False),
        })
    return jsonify({"cells": cells})
