"""Polls GLOBAL_STATE_HUB marks and emits coalesced mark_update events.

Coalescing: for any slug whose price moved since last emission, emit at
most one mark_update per coalesce-interval. Protects the browser from
CLOB burst traffic.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

from dugout_dash.events import EventBus, GLOBAL_EVENT_BUS

logger = logging.getLogger("dugout.market_tap")


class MarketTap:
    def __init__(self, bus: EventBus | None = None, interval_sec: float = 0.2) -> None:
        self.bus = bus or GLOBAL_EVENT_BUS
        self.interval = interval_sec
        self._last_emitted: dict[str, float] = {}
        self._pending: dict[str, float] = {}
        self._last_flush = 0.0
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def feed(self, marks: dict[str, dict[str, Any]]) -> None:
        """marks: {slug: {current_price, best_bid, best_ask, ...}}"""
        for slug, row in marks.items():
            px = row.get("current_price")
            if px is None:
                continue
            self._pending[slug] = float(px)

    def flush_if_due(self, now: float | None = None) -> None:
        now = now if now is not None else time.monotonic()
        if now - self._last_flush < self.interval:
            return
        self._last_flush = now
        for slug, mark in list(self._pending.items()):
            prev = self._last_emitted.get(slug)
            if prev is not None and abs(mark - prev) < 1e-9:
                continue
            self.bus.publish("mark_update", {
                "slug": slug,
                "mark": mark,
                "prev_mark": prev,
                "ts": time.time(),
            })
            self._last_emitted[slug] = mark
        self._pending.clear()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="dugout-market-tap", daemon=True)
        self._thread.start()
        logger.info("market_tap thread started (interval=%.2fs)", self.interval)

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        from core.state_hub import GLOBAL_STATE_HUB
        while not self._stop.is_set():
            try:
                snap = GLOBAL_STATE_HUB.snapshot()
                self.feed(snap)
                self.flush_if_due()
            except Exception as e:
                logger.warning("market_tap loop error: %s", e)
            time.sleep(min(self.interval / 2, 0.1))


GLOBAL_MARKET_TAP = MarketTap()
