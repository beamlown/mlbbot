"""market_tap coalescing — at most one mark_update per slug per interval."""
import time

from dugout_dash.events import EventBus
from dugout_dash.market_tap import MarketTap


def test_single_slug_burst_coalesces_to_one_per_interval():
    bus = EventBus()
    q = bus.subscribe()
    tap = MarketTap(bus=bus, interval_sec=0.2)

    for i in range(50):
        tap.feed({"foo": {"current_price": 0.50 + i * 0.001}})

    tap.flush_if_due()
    frames = []
    while not q.empty():
        frames.append(q.get_nowait())
    assert len(frames) == 1
    assert frames[0]["type"] == "mark_update"
    assert frames[0]["payload"]["slug"] == "foo"
    assert abs(frames[0]["payload"]["mark"] - 0.549) < 1e-6


def test_multi_slug_burst_one_event_per_slug():
    bus = EventBus()
    q = bus.subscribe()
    tap = MarketTap(bus=bus, interval_sec=0.2)

    tap.feed({
        "foo": {"current_price": 0.5},
        "bar": {"current_price": 0.7},
        "baz": {"current_price": 0.9},
    })
    tap.flush_if_due()
    slugs = set()
    while not q.empty():
        slugs.add(q.get_nowait()["payload"]["slug"])
    assert slugs == {"foo", "bar", "baz"}


def test_no_emission_when_price_unchanged():
    bus = EventBus()
    q = bus.subscribe()
    tap = MarketTap(bus=bus, interval_sec=0.2)

    tap.feed({"foo": {"current_price": 0.5}})
    tap.flush_if_due()
    while not q.empty():
        q.get_nowait()

    time.sleep(0.25)
    tap.feed({"foo": {"current_price": 0.5}})
    tap.flush_if_due()
    assert q.empty()
