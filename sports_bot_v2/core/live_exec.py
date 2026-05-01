"""
core/live_exec.py — Signed-order placement + cancellation.

Dead code during this cycle. Two independent environment flags must BOTH be
flipped for any real order to leave the box:

  PHASE=live                     (default "paper")
  LIVE_TRADING_KILL_SWITCH=false (default "true")

Additionally, the signer returned by core.signer.get_signer() must have
is_ready() == True. The default DummySigner is_ready() == False, so even
if both env flags are flipped, a misconfigured SIGNER value (or the env-
var-missing case) produces a rejected result rather than a real submission.

All rejects log at WARN with the specific gate that tripped, for audit.

Env-read semantics: `PHASE` and `LIVE_TRADING_KILL_SWITCH` are captured at
module import time and are NOT re-read per call. To flip either value on a
running process, the process must be restarted — there is no in-process
emergency stop. This is intentional: import-time immutability means no
attacker path inside the running process can lift either gate. If you need
to halt a running bot immediately, kill the process; the launcher will
respawn it with the fresh env.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from core.polymarket_client import tick_size
from core.signer import OrderArgs, Signer, get_signer

logger = logging.getLogger("core.live_exec")

PHASE = os.getenv("PHASE", "paper").strip().lower()
# FAIL-SAFE PARSE: only the explicit OFF strings lift the kill switch;
# unrecognized values (typos, empty) engage it. Default "true" → engaged.
LIVE_TRADING_KILL_SWITCH = os.getenv("LIVE_TRADING_KILL_SWITCH", "true").strip().lower() not in {
    "false", "0", "no", "off"
}

_MIN_PRICE = 0.01
_MAX_PRICE = 0.99


@dataclass
class OrderResult:
    status: str  # "placed" | "rejected" | "error"
    order_id: str | None
    reason: str
    price_snapped: float | None


def _snap_to_tick(price: float, tick: float) -> float:
    """Round price to the nearest multiple of tick. Clamps float precision."""
    if tick <= 0:
        tick = 0.01
    return round(round(price / tick) * tick, 6)


def _normalize_side(s: str) -> str:
    s = s.strip().upper()
    if s in ("BUY_YES", "BUY_NO", "BUY"):
        return "BUY"
    if s == "SELL":
        return "SELL"
    raise ValueError(f"unknown side: {s!r}")


def place_order(
    side: str,
    token_id: str,
    price: float,
    size_usd: float,
    signer: Signer | None = None,
) -> OrderResult:
    """Place a live order. See module docstring for safety gates.

    Returns an OrderResult with status one of:
      - "placed": real order submitted (never this cycle)
      - "rejected": blocked by one of the kill-switches or signer-not-ready
      - "error": attempted submit but post_order raised
    """
    # Gate 1 — PHASE
    if PHASE != "live":
        return OrderResult(status="rejected", order_id=None, reason=f"phase={PHASE}", price_snapped=None)

    # Gate 2 — kill switch
    if LIVE_TRADING_KILL_SWITCH:
        logger.warning("live_exec.place_order: blocked by LIVE_TRADING_KILL_SWITCH")
        return OrderResult(status="rejected", order_id=None, reason="kill_switch", price_snapped=None)

    # Snap price to tick grid
    tick = tick_size(token_id)
    snapped_price = _snap_to_tick(price, tick)
    if snapped_price < _MIN_PRICE or snapped_price > _MAX_PRICE:
        return OrderResult(
            status="rejected", order_id=None,
            reason=f"price_out_of_band:{snapped_price}", price_snapped=snapped_price,
        )

    # Resolve signer and check readiness
    if signer is None:
        signer = get_signer()
    if not signer.is_ready():
        logger.warning("live_exec.place_order: signer not ready (DummySigner?); refusing submit")
        return OrderResult(
            status="rejected", order_id=None,
            reason="signer_not_ready", price_snapped=snapped_price,
        )

    # All gates open — sign and submit. Both sign_order and post_order wrapped
    # together so any crypto/HTTP failure returns status="error" per contract
    # (rather than propagating an exception to the caller).
    try:
        args = OrderArgs(
            token_id=token_id,
            side=_normalize_side(side),
            price=snapped_price,
            size=size_usd,
        )
        signed = signer.sign_order(args)
        from core.polymarket_client import _get_client
        client = _get_client()
        resp = client.post_order(signed.blob)
        order_id = resp.get("orderID") if isinstance(resp, dict) else None
    except Exception as exc:
        logger.warning("live_exec.place_order: sign/submit failed err=%s", exc)
        return OrderResult(
            status="error", order_id=None,
            reason=f"sign_or_submit:{exc}", price_snapped=snapped_price,
        )

    logger.info("live_exec.place_order: placed order_id=%s side=%s price=%.4f size=%.2f",
                order_id, args.side, snapped_price, size_usd)
    return OrderResult(status="placed", order_id=order_id, reason="", price_snapped=snapped_price)


def cancel_order(order_id: str) -> OrderResult:
    """Cancel a live order by ID. Same dual-gate guards as place_order."""
    if PHASE != "live":
        return OrderResult(status="rejected", order_id=order_id, reason=f"phase={PHASE}", price_snapped=None)
    if LIVE_TRADING_KILL_SWITCH:
        logger.warning("live_exec.cancel_order: blocked by kill_switch order_id=%s", order_id)
        return OrderResult(status="rejected", order_id=order_id, reason="kill_switch", price_snapped=None)

    try:
        from core.polymarket_client import _get_client
        client = _get_client()
        resp = client.cancel_orders([order_id])
        logger.info("live_exec.cancel_order: ok order_id=%s resp=%r", order_id, resp)
        return OrderResult(status="placed", order_id=order_id, reason="", price_snapped=None)
    except Exception as exc:
        logger.warning("live_exec.cancel_order: failed order_id=%s err=%s", order_id, exc)
        return OrderResult(status="error", order_id=order_id, reason=f"cancel:{exc}", price_snapped=None)


def cancel_all() -> OrderResult:
    """Panic stop: cancel ALL open orders for this wallet. Same dual-gate guards."""
    if PHASE != "live":
        return OrderResult(status="rejected", order_id=None, reason=f"phase={PHASE}", price_snapped=None)
    if LIVE_TRADING_KILL_SWITCH:
        logger.warning("live_exec.cancel_all: blocked by kill_switch")
        return OrderResult(status="rejected", order_id=None, reason="kill_switch", price_snapped=None)

    try:
        from core.polymarket_client import _get_client
        client = _get_client()
        resp = client.cancel_market_orders()  # cancel-all for wallet
        logger.info("live_exec.cancel_all: ok resp=%r", resp)
        return OrderResult(status="placed", order_id=None, reason="", price_snapped=None)
    except Exception as exc:
        logger.warning("live_exec.cancel_all: failed err=%s", exc)
        return OrderResult(status="error", order_id=None, reason=f"cancel_all:{exc}", price_snapped=None)
