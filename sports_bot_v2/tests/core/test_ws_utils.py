"""Tests for core.ws_utils.run_with_reconnect."""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest


def test_run_with_reconnect_stops_on_event():
    """When stop_event is set, run_with_reconnect must exit cleanly."""
    from core import ws_utils

    stop_event = threading.Event()
    ws_factory = MagicMock()
    fake_ws = MagicMock()
    fake_ws.run_forever = MagicMock(return_value=None)  # Connection "dropped"
    ws_factory.return_value = fake_ws

    def runner():
        ws_utils.run_with_reconnect(
            ws_factory=ws_factory,
            stop_event=stop_event,
            reconnect_delay=0.01,
            logger_name="test",
        )

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    time.sleep(0.1)  # Let it cycle a few reconnects
    stop_event.set()
    thread.join(timeout=2.0)

    assert not thread.is_alive(), "run_with_reconnect should exit when stop_event set"
    assert ws_factory.call_count >= 1


def test_run_with_reconnect_increments_counter_on_each_reconnect():
    """The on_reconnect callback is invoked each time run_forever returns."""
    from core import ws_utils

    stop_event = threading.Event()
    reconnect_count = {"n": 0}

    def on_reconnect():
        reconnect_count["n"] += 1
        if reconnect_count["n"] >= 3:
            stop_event.set()

    ws_factory = MagicMock()
    fake_ws = MagicMock()
    fake_ws.run_forever = MagicMock(return_value=None)
    ws_factory.return_value = fake_ws

    ws_utils.run_with_reconnect(
        ws_factory=ws_factory,
        stop_event=stop_event,
        reconnect_delay=0.01,
        on_reconnect=on_reconnect,
        logger_name="test",
    )

    assert reconnect_count["n"] >= 3


def test_run_with_reconnect_swallows_run_forever_exceptions():
    """An exception from run_forever must be caught, logged, and followed by
    another reconnect attempt — not propagate out and kill the worker thread."""
    from core import ws_utils

    stop_event = threading.Event()
    call_count = {"n": 0}

    def exploding_run_forever(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] >= 2:
            stop_event.set()
            return None
        raise ConnectionError("simulated network hiccup")

    ws_factory = MagicMock()
    fake_ws = MagicMock()
    fake_ws.run_forever = exploding_run_forever
    ws_factory.return_value = fake_ws

    ws_utils.run_with_reconnect(
        ws_factory=ws_factory,
        stop_event=stop_event,
        reconnect_delay=0.01,
        logger_name="test",
    )

    # Second call succeeded after first raised — proves exception swallowed
    assert call_count["n"] >= 2


def test_run_with_reconnect_sleeps_between_reconnects(monkeypatch):
    """Between reconnect attempts, time.sleep is called with reconnect_delay."""
    from core import ws_utils

    stop_event = threading.Event()
    sleeps: list[float] = []

    def fake_sleep(secs):
        sleeps.append(secs)
        if len(sleeps) >= 2:
            stop_event.set()

    monkeypatch.setattr(ws_utils.time, "sleep", fake_sleep)

    ws_factory = MagicMock()
    fake_ws = MagicMock()
    fake_ws.run_forever = MagicMock(return_value=None)
    ws_factory.return_value = fake_ws

    ws_utils.run_with_reconnect(
        ws_factory=ws_factory,
        stop_event=stop_event,
        reconnect_delay=5.0,
        logger_name="test",
    )

    assert sleeps and sleeps[0] == 5.0
