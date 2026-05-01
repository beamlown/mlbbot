"""
core/account_sync.py — Boot-time account state reconciliation.

Runs once at bot_core startup, right after init_db(). Queries Polymarket's
authenticated endpoints to:
  1. Fetch current USDC balance and warn if below 2× MAX_POSITION_SIZE_USD
  2. Fetch my open orders + my recent trade history
  3. Diff against local sqlite trades table; log any drift

Paper-mode behavior: no API creds available (polymarket_auth raises for
DummySigner), so all three public functions return immediately with a
"no wallet, skipping" log line. Zero HTTP, zero side effects.

Live-mode behavior (future, with PrivateKeySigner + real wallet):
reconcile_positions_on_boot() logs a drift report comparing server-side
open orders to local status='open'/'pending' rows. Mismatches don't
auto-correct — the operator decides whether to cancel orphan orders,
open missing rows, etc.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("core.account_sync")

MIN_BALANCE_WARN_USD = float(os.getenv("MIN_BALANCE_WARN_USD", "50.0"))


# Re-export for test patchability — tests patch "core.account_sync.get_my_orders" etc.
try:
    from core.polymarket_client import get_my_orders, get_my_trades, get_balance_allowance
except ImportError:  # polymarket_client not importable at module load — fail later if used
    get_my_orders = None  # type: ignore
    get_my_trades = None  # type: ignore
    get_balance_allowance = None  # type: ignore


def _get_creds() -> dict[str, str] | None:
    """Return cached API creds or None if none available.

    In paper mode with DummySigner, polymarket_auth.provision_api_credentials
    raises — we catch and return None so the caller can log+skip cleanly
    without re-raising through the boot sequence.
    """
    try:
        from core.polymarket_auth import provision_api_credentials
        from core.signer import get_signer
        return provision_api_credentials(get_signer())
    except Exception as exc:
        logger.debug("account_sync: no creds available (%s)", exc)
        return None


def reconcile_positions_on_boot() -> dict | None:
    """Run the full reconcile pass. Returns a drift-report dict on success,
    None if skipped (paper mode).

    Report shape:
      {
        "matched": int,
        "orphan_local": list[str],   # order_ids we have locally but server doesn't
        "orphan_server": list[str],  # order_ids server has but we don't
      }
    """
    creds = _get_creds()
    if creds is None:
        logger.info("account_sync: no wallet, skipping boot reconcile")
        return None
    logger.info("account_sync: reconcile starting (live mode)")

    from core.db import fetch_open_trades

    local_rows = fetch_open_trades()
    local_order_ids = {str(r.order_id): r for r in local_rows if r.order_id}
    try:
        server_orders = get_my_orders()
    except Exception as exc:
        logger.warning("account_sync: get_my_orders failed err=%s", exc)
        server_orders = []
    try:
        _ = get_my_trades(since_ts=0)  # warm cache / surface errors; not used here
    except Exception as exc:
        logger.warning("account_sync: get_my_trades failed err=%s", exc)

    server_order_ids = {str(o.get("id") or o.get("order_id") or "") for o in server_orders if isinstance(o, dict)}
    server_order_ids.discard("")

    orphan_local = sorted(local_order_ids.keys() - server_order_ids)
    orphan_server = sorted(server_order_ids - local_order_ids.keys())
    matched = len(local_order_ids.keys() & server_order_ids)

    for oid in orphan_local:
        logger.warning("account_sync: drift:orphan_local order_id=%s slug=%s",
                       oid, local_order_ids[oid].market_slug)
    for oid in orphan_server:
        logger.warning("account_sync: drift:orphan_server order_id=%s", oid)
    if not orphan_local and not orphan_server:
        logger.info("account_sync: reconcile OK — matched=%d no drift", matched)
    else:
        logger.info("account_sync: reconcile done — matched=%d orphan_local=%d orphan_server=%d",
                    matched, len(orphan_local), len(orphan_server))

    return {
        "matched": matched,
        "orphan_local": orphan_local,
        "orphan_server": orphan_server,
    }


def fetch_balance() -> float | None:
    """Return wallet USDC balance, or None if skipped (paper mode).
    Warns if below MIN_BALANCE_WARN_USD (default 50.0)."""
    creds = _get_creds()
    if creds is None:
        return None
    bal = get_balance_allowance()
    if bal is None:
        logger.warning("account_sync: balance fetch returned None")
        return None
    if bal < MIN_BALANCE_WARN_USD:
        logger.warning(
            "account_sync: balance=%.2f below threshold %.2f — consider refunding",
            bal, MIN_BALANCE_WARN_USD,
        )
    else:
        logger.info("account_sync: balance=%.2f USDC (threshold %.2f)", bal, MIN_BALANCE_WARN_USD)
    return bal


def sync_trades_history(since_ts: int) -> int:
    """Sync my trades from since_ts, log any orphan fills (server has,
    we don't). Returns count of trades processed.

    Does NOT insert rows — Stair B's user_stream handles fills via TRADE events.
    This is a catch-up safety net that surfaces drift at boot.
    """
    creds = _get_creds()
    if creds is None:
        return 0
    from core.db import fetch_open_trades

    try:
        trades = get_my_trades(since_ts=since_ts)
    except Exception as exc:
        logger.warning("account_sync: get_my_trades failed err=%s", exc)
        return 0

    local_rows = fetch_open_trades()
    local_order_ids = {str(r.order_id) for r in local_rows if r.order_id}

    orphan_count = 0
    for t in trades:
        if not isinstance(t, dict):
            continue
        makers = t.get("maker_orders") or []
        if not isinstance(makers, list):
            continue
        for maker in makers:
            if not isinstance(maker, dict):
                continue
            oid = str(maker.get("order_id") or "")
            if oid and oid not in local_order_ids:
                logger.warning(
                    "account_sync: orphan_fill order_id=%s trade_id=%s — server reports fill, no local row",
                    oid, t.get("id"),
                )
                orphan_count += 1

    logger.info("account_sync: sync_trades_history processed=%d orphan_fills=%d",
                len(trades), orphan_count)
    return len(trades)
