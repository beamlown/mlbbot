"""In-process pub/sub bus for dugout_dash.

Publish is non-blocking: if a subscriber's queue is full the oldest frame
is dropped. Subscribers get a bounded queue they drain on their own
schedule (typically one SSE connection per subscriber).
"""
from __future__ import annotations

import queue
import threading
from typing import Any


class EventBus:
    def __init__(self, max_queue_size: int = 256) -> None:
        self._max = max_queue_size
        self._subs: list[queue.Queue] = []
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=self._max)
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            try:
                self._subs.remove(q)
            except ValueError:
                pass

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subs)

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        frame = {"type": event_type, "payload": payload}
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            self._offer(q, frame)

    def _offer(self, q: queue.Queue, frame: dict) -> None:
        try:
            q.put_nowait(frame)
        except queue.Full:
            try:
                q.get_nowait()
            except queue.Empty:
                pass
            try:
                q.put_nowait(frame)
            except queue.Full:
                pass


GLOBAL_EVENT_BUS = EventBus()
