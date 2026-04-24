"""SSE endpoint smoke test — connects, receives a published event, disconnects."""
import threading
import time

import pytest

from dugout_dash import create_app
from dugout_dash.events import GLOBAL_EVENT_BUS


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_sse_receives_published_event(client):
    chunks: list[bytes] = []

    def reader():
        with client.get("/api/events", buffered=False) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("Content-Type", "")
            deadline = time.monotonic() + 2.0
            for chunk in resp.response:
                chunks.append(chunk)
                if time.monotonic() > deadline:
                    break

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    time.sleep(0.3)

    GLOBAL_EVENT_BUS.publish("test_event", {"hello": "world"})
    t.join(timeout=3.0)

    body = b"".join(chunks).decode()
    assert "event: test_event" in body
    assert '"hello": "world"' in body or '"hello":"world"' in body
