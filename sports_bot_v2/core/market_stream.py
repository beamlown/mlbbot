from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

import websocket

from core.state_hub import GLOBAL_STATE_HUB

logger = logging.getLogger("market_stream")

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
PING_INTERVAL_SEC = 10


class MarketStreamClient:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._ws: websocket.WebSocketApp | None = None
        self._tracked: dict[str, dict[str, str]] = {}
        self._lock = threading.Lock()
        self._connected = False
        self._last_subscribe_payload: dict[str, Any] | None = None
        self._last_open_ts: float | None = None
        self._last_message_ts: float | None = None
        self._last_message_type: str | None = None
        self._last_error: str | None = None
        self._last_state_hub_update_ts: float | None = None
        self._last_state_hub_update_slug: str | None = None
        self._mark_count_received = 0
        self._parser_hit_count = 0
        self._parser_miss_count = 0
        self._reconnect_count = 0

    def update_tracked_assets(self, tracked: dict[str, dict[str, str]]) -> bool:
        with self._lock:
            changed = self._tracked != dict(tracked)
            self._tracked = dict(tracked)
        if changed and self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        return changed

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            logger.info("market_stream: start skipped, thread already alive")
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="market-stream", daemon=True)
        self._thread.start()
        logger.info("market_stream: worker thread started")

    def stop(self) -> None:
        self._stop.set()
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass

    def _subscription_payload(self) -> dict[str, Any] | None:
        with self._lock:
            asset_ids = [v["asset_id"] for v in self._tracked.values() if v.get("asset_id")]
        if not asset_ids:
            return None
        return {
            "assets_ids": asset_ids,
            "type": "market",
            "custom_feature_enabled": True,
        }

    def _on_open(self, ws: websocket.WebSocketApp) -> None:
        self._connected = True
        self._last_open_ts = time.time()
        logger.info("market_stream: websocket opened")
        payload = self._subscription_payload()
        self._last_subscribe_payload = payload
        if payload:
            logger.info("market_stream: subscribe payload=%s", json.dumps(payload))
            ws.send(json.dumps(payload))
        else:
            logger.warning("market_stream: websocket opened with empty subscription payload")

    def _on_message(self, ws: websocket.WebSocketApp, message: str) -> None:
        try:
            data = json.loads(message)
        except Exception:
            logger.warning("market_stream: non-json message received")
            return
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                self._parser_miss_count += 1
                continue
            event_type = item.get("event_type") or item.get("type") or item.get("event")
            self._last_message_ts = time.time()
            self._last_message_type = str(event_type)
            logger.debug("market_stream: message event_type=%s keys=%s", event_type, sorted(list(item.keys()))[:12])
            if event_type == "PONG":
                continue

            # Polymarket market-channel shapes we accept:
            #  (A) book / top-of-book: top-level asset_id + best_bid / best_ask / last_trade_price
            #  (B) price_change: nested `price_changes` array of per-side updates; each entry carries asset_id + price + side + best_bid/best_ask
            #  (C) tick_size_change / other: no price data, skip
            sub_updates: list[dict] = []
            pc = item.get("price_changes")
            if isinstance(pc, list) and pc:
                for ch in pc:
                    if isinstance(ch, dict):
                        sub_updates.append(ch)
            else:
                sub_updates.append(item)

            for upd in sub_updates:
                asset_id = str(
                    upd.get("asset_id") or upd.get("assetID") or upd.get("asset_id_hex")
                    or item.get("asset_id") or ""
                )
                if not asset_id:
                    self._parser_miss_count += 1
                    continue
                with self._lock:
                    tracked = next((v for v in self._tracked.values() if v.get("asset_id") == asset_id), None)
                if not tracked:
                    self._parser_miss_count += 1
                    continue
                best_bid = _to_float(upd.get("best_bid") or upd.get("bid") or upd.get("bestBid"))
                best_ask = _to_float(upd.get("best_ask") or upd.get("ask") or upd.get("bestAsk"))
                last_trade = _to_float(
                    upd.get("last_trade_price") or upd.get("price") or upd.get("lastTradePrice")
                )
                # price_change entries often carry `price` + `side`; that's a side-specific touch.
                # Use it as last_trade proxy (executable-at price) when last_trade isn't provided.
                current_price = last_trade if last_trade is not None else (best_bid if best_bid is not None else best_ask)
                spread = None
                if best_bid is not None and best_ask is not None:
                    spread = round(best_ask - best_bid, 6)
                GLOBAL_STATE_HUB.update_mark(
                    market_slug=tracked["market_slug"],
                    market_id=tracked["market_id"],
                    asset_id=asset_id,
                    current_price=current_price,
                    best_bid=best_bid,
                    best_ask=best_ask,
                    spread=spread,
                    source="polymarket_stream",
                )
                self._mark_count_received += 1
                self._parser_hit_count += 1
                self._last_state_hub_update_ts = time.time()
                self._last_state_hub_update_slug = tracked["market_slug"]
                logger.debug(
                    "market_stream: state_hub updated slug=%s asset_id=%s current_price=%s",
                    tracked["market_slug"], asset_id, current_price,
                )

    def _on_error(self, ws: websocket.WebSocketApp, error: Any) -> None:
        self._last_error = str(error)
        logger.warning("market_stream: websocket error=%s", error)

    def _on_close(self, ws: websocket.WebSocketApp, *args: Any) -> None:
        self._connected = False
        logger.warning("market_stream: websocket closed args=%s", args)

    def _run(self) -> None:
        while not self._stop.is_set():
            payload = self._subscription_payload()
            if not payload:
                logger.info("market_stream: no tracked assets, waiting")
                time.sleep(2)
                continue
            self._ws = websocket.WebSocketApp(
                WS_URL,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )
            ping_thread = threading.Thread(target=self._ping_loop, daemon=True)
            ping_thread.start()
            try:
                logger.info("market_stream: run_forever starting")
                self._ws.run_forever()
            except Exception as exc:
                logger.warning("market_stream: run_forever exception=%s", exc)
            self._reconnect_count += 1
            time.sleep(3)

    def _ping_loop(self) -> None:
        while not self._stop.is_set() and self._ws:
            try:
                self._ws.send("PING")
                logger.info("market_stream: PING sent")
            except Exception as exc:
                logger.warning("market_stream: ping failed error=%s", exc)
                return
            time.sleep(PING_INTERVAL_SEC)

    def debug_status(self) -> dict[str, Any]:
        with self._lock:
            tracked_sample = list(self._tracked.values())[:5]
            tracked_count = len(self._tracked)
        return {
            "stream_enabled": True,
            "thread_alive": bool(self._thread and self._thread.is_alive()),
            "connected": self._connected,
            "tracked_asset_count": tracked_count,
            "tracked_assets_sample": tracked_sample,
            "last_subscribe_payload": self._last_subscribe_payload,
            "last_open_ts": self._last_open_ts,
            "last_message_ts": self._last_message_ts,
            "last_message_type": self._last_message_type,
            "last_error": self._last_error,
            "last_state_hub_update_ts": self._last_state_hub_update_ts,
            "last_state_hub_update_slug": self._last_state_hub_update_slug,
            "mark_count_received": self._mark_count_received,
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


GLOBAL_MARKET_STREAM = MarketStreamClient()
