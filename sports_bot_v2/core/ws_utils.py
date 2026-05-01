"""
core/ws_utils.py — Shared websocket reconnect loop.

Extracted from market_stream.py::_run. Both MarketStreamClient and
UserStreamClient (Stair B) delegate their outer reconnect loop here so
there's one proven implementation of the pattern.

The client owns:
  - Building its own `WebSocketApp` (on_open/on_message/on_error/on_close closures)
  - Its own subscription payload and tracked-asset state

This module owns ONLY the "call run_forever, reconnect on return/exception,
respect stop_event" loop.
"""
from __future__ import annotations

import logging
import time
from typing import Callable

import websocket  # noqa: F401  — imported for type-hint clarity in callers


def run_with_reconnect(
    *,
    ws_factory: Callable[[], "websocket.WebSocketApp"],
    stop_event,
    reconnect_delay: float = 3.0,
    on_reconnect: Callable[[], None] | None = None,
    logger_name: str = "ws_utils",
) -> None:
    """Run a websocket in a reconnect-until-stopped loop.

    Args:
      ws_factory: called each reconnect; must return a fresh WebSocketApp.
      stop_event: a threading.Event; set it to terminate the loop.
      reconnect_delay: seconds to sleep between reconnects.
      on_reconnect: optional callback invoked after each disconnect, before
                    sleeping. Useful for the caller to increment a counter
                    or update debug_status.
      logger_name: logger namespace for this runner's messages.

    Exceptions raised inside `run_forever` are caught and logged at WARN;
    the loop continues to the next reconnect. Exceptions inside `ws_factory`
    propagate (the caller's subscription state is broken; can't recover).
    """
    logger = logging.getLogger(logger_name)
    while not stop_event.is_set():
        ws = ws_factory()
        try:
            logger.info("%s: run_forever starting", logger_name)
            ws.run_forever()
        except Exception as exc:
            logger.warning("%s: run_forever exception=%s", logger_name, exc)
        if on_reconnect is not None:
            try:
                on_reconnect()
            except Exception as exc:
                logger.warning("%s: on_reconnect callback raised=%s", logger_name, exc)
        if stop_event.is_set():
            break
        time.sleep(reconnect_delay)
