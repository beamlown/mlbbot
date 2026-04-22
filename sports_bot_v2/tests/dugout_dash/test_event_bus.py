"""EventBus tests — publish/subscribe/unsubscribe + overflow behavior."""
import time

import pytest

from dugout_dash.events import EventBus


def test_publish_delivers_to_single_subscriber():
    bus = EventBus()
    q = bus.subscribe()
    bus.publish("trade_entered", {"id": 42})
    evt = q.get(timeout=0.5)
    assert evt == {"type": "trade_entered", "payload": {"id": 42}}


def test_publish_fans_out_to_all_subscribers():
    bus = EventBus()
    q1, q2, q3 = bus.subscribe(), bus.subscribe(), bus.subscribe()
    bus.publish("mark_update", {"slug": "foo", "mark": 0.5})
    for q in (q1, q2, q3):
        evt = q.get(timeout=0.5)
        assert evt["type"] == "mark_update"
        assert evt["payload"]["slug"] == "foo"


def test_unsubscribe_removes_queue():
    bus = EventBus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()
    bus.unsubscribe(q1)
    bus.publish("x", {})
    assert q2.qsize() == 1
    assert q1.qsize() == 0


def test_overflow_drops_oldest_when_queue_full():
    bus = EventBus(max_queue_size=3)
    q = bus.subscribe()
    for i in range(5):
        bus.publish("tick", {"i": i})
    received = [q.get_nowait()["payload"]["i"] for _ in range(3)]
    assert received == [2, 3, 4]


def test_publish_is_nonblocking_under_load():
    bus = EventBus(max_queue_size=10)
    bus.subscribe()
    start = time.monotonic()
    for _ in range(1000):
        bus.publish("x", {})
    elapsed = time.monotonic() - start
    assert elapsed < 0.5, f"publish blocked for {elapsed:.3f}s under back-pressure"
