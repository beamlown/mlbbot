"""
core/user_stream.py — Polymarket user-channel websocket subscriber.

Subscribes to wss://ws-subscriptions-clob.polymarket.com/ws/user with API
credentials derived via polymarket_auth.provision_api_credentials. Receives
TRADE events (our orders got filled) and ORDER events (our order status
changed: new/matched/cancelled/expired).

TRADE handler → db.update_trade_fill(order_id, actual_fill_px) → sqlite row
transitions status='pending' → status='open' with real fill price.
ORDER handler → logs the transition. Row updates from order events are
deferred to a future task (this cycle logs only).

Dead code by default. bot_core only calls UserStreamClient.start() when
USER_STREAM_MIRROR=true OR PHASE=live. With no creds passed or no signer
able to derive them, start() is a warn-and-noop.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

import websocket

from core.ws_utils import run_with_reconnect
from core.db import update_trade_fill

logger = logging.getLogger("core.user_stream")

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/user"
PING_INTERVAL_SEC = 10


class UserStreamClient:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._ws: websocket.WebSocketApp | None = None
        self._api_creds: dict[str, str] | None = None
        self._lock = threading.Lock()
        self._connected = False
        self._last_message_ts: float | None = None
        self._last_message_type: str | None = None
        self._trade_events_seen = 0
        self._order_events_seen = 0
        self._parser_hit_count = 0
        self._parser_miss_count = 0
        self._reconnect_count = 0

    def start(self, api_creds: dict[str, str] | None) -> None:
        if not api_creds:
            logger.warning("user_stream: no api_creds provided, start() is a no-op")
            return
        if self._thread and self._thread.is_alive():
            logger.info("user_stream: start skipped, thread already alive")
            return
        self._api_creds = dict(api_creds)
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="user-stream", daemon=True)
        self._thread.start()
        logger.info("user_stream: worker thread started")

    def stop(self) -> None:
        self._stop.set()
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass

    def _subscription_payload(self) -> dict[str, Any] | None:
        if not self._api_creds:
            return None
        return {
            "auth": {
                "apiKey": self._api_creds["apiKey"],
                "secret": self._api_creds["secret"],
                "passphrase": self._api_creds["passphrase"],
            },
            "type": "user",
            "markets": [],  # Empty = subscribe to all user events
        }

    def _on_open(self, ws: websocket.WebSocketApp) -> None:
        self._connected = True
        payload = self._subscription_payload()
        if payload:
            ws.send(json.dumps(payload))
            logger.info("user_stream: subscribed (auth present)")

    def _on_message(self, ws, message: str) -> None:
        try:
            data = json.loads(message)
        except Exception:
            logger.warning("user_stream: non-json message received")
            return
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                self._parser_miss_count += 1
                continue
            event_type = str(item.get("event_type") or item.get("type") or "").lower()
            self._last_message_ts = time.time()
            self._last_message_type = event_type
            if event_type == "pong":
                continue
            if event_type == "trade":
                self._handle_trade(item)
                self._trade_events_seen += 1
                self._parser_hit_count += 1
            elif event_type == "order":
                self._handle_order(item)
                self._order_events_seen += 1
                self._parser_hit_count += 1
            else:
                self._parser_miss_count += 1

    def _handle_trade(self, event: dict) -> None:
        """Match TRADE event back to our sqlite pending row via maker_orders[].order_id."""
        makers = event.get("maker_orders") or []
        if not isinstance(makers, list):
            logger.warning("user_stream: trade event has non-list maker_orders: %r", event)
            return
        # Event-level price as fallback fill price
        event_price = _to_float(event.get("price"))
        for maker in makers:
            if not isinstance(maker, dict):
                continue
            order_id = str(maker.get("order_id") or "")
            if not order_id:
                continue
            # Prefer the maker's own price if present
            fill_px = _to_float(maker.get("price")) or event_price
            if fill_px is None:
                logger.warning("user_stream: trade event for order=%s has no parseable price", order_id)
                continue
            row_id = update_trade_fill(order_id=order_id, actual_fill_px=fill_px)
            if row_id is not None:
                logger.info(
                    "user_stream: TRADE order_id=%s fill_px=%.4f row_id=%d",
                    order_id, fill_px, row_id,
                )
            else:
                logger.info(
                    "user_stream: TRADE order_id=%s unknown — no row matched",
                    order_id,
                )

    def _handle_order(self, event: dict) -> None:
        """Log ORDER status transitions. Row updates deferred to future task."""
        order_id = str(event.get("id") or event.get("order_id") or "")
        status = str(event.get("status") or "").upper()
        logger.info("user_stream: ORDER order_id=%s status=%s", order_id, status)

    def _on_error(self, ws: websocket.WebSocketApp, error: Any) -> None:
        logger.warning("user_stream: websocket error=%s", error)

    def _on_close(self, ws: websocket.WebSocketApp, *args: Any) -> None:
        self._connected = False
        logger.warning("user_stream: websocket closed args=%s", args)

    def _run(self) -> None:
        def _factory() -> websocket.WebSocketApp:
            self._ws = websocket.WebSocketApp(
                WS_URL,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )
            ping_thread = threading.Thread(target=self._ping_loop, daemon=True)
            ping_thread.start()
            return self._ws

        def _on_reconnect() -> None:
            self._reconnect_count += 1

        run_with_reconnect(
            ws_factory=_factory,
            stop_event=self._stop,
            reconnect_delay=3.0,
            on_reconnect=_on_reconnect,
            logger_name="user_stream",
        )

    def _ping_loop(self) -> None:
        while not self._stop.is_set() and self._ws:
            try:
                self._ws.send("PING")
            except Exception:
                return
            time.sleep(PING_INTERVAL_SEC)

    def debug_status(self) -> dict[str, Any]:
        return {
            "stream_enabled": True,
            "thread_alive": bool(self._thread and self._thread.is_alive()),
            "connected": self._connected,
            "last_message_ts": self._last_message_ts,
            "last_message_type": self._last_message_type,
            "trade_events_seen": self._trade_events_seen,
            "order_events_seen": self._order_events_seen,
            "parser_hit_count": self._parser_hit_count,
            "parser_miss_count": self._parser_miss_count,
            "reconnect_count": self._reconnect_count,
        }


def _to_float(v: Any) -> float | None:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None


GLOBAL_USER_STREAM = UserStreamClient()
