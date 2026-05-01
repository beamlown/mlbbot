"""
core/polymarket_auth.py — API credential provisioning for Polymarket user endpoints.

The CLOB's user-channel websocket (ws/user) requires an API key/secret/passphrase
triple. Polymarket derives these from an EOA private key via EIP-712 signed
challenge (py_clob_client.ClobClient.create_or_derive_api_key()).

This module scaffolds that provisioning. In Stair B we never actually call it
with a real signer — DummySigner raises explicitly because its signatures are
not valid EIP-712 payloads; the CLOB would reject them. A future production
task wires PrivateKeySigner to produce a real derive call.

Creds are cached to runtime/polymarket_creds.json (gitignored). The cache
avoids re-deriving on every restart (the derive requires a wallet signature
the operator may not want to repeat).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from py_clob_client.client import ClobClient

from core.signer import DummySigner, Signer

logger = logging.getLogger("core.polymarket_auth")

CLOB_HOST = os.getenv("CLOB_HOST", "https://clob.polymarket.com")
POLYGON_CHAIN_ID = int(os.getenv("POLYGON_CHAIN_ID", "137"))
CREDS_CACHE_PATH = Path(os.getenv("POLYMARKET_CREDS_CACHE_PATH", "runtime/polymarket_creds.json"))


def provision_api_credentials(signer: Signer) -> dict[str, str]:
    """Return cached API creds or derive + cache fresh ones.

    Raises:
        RuntimeError: if signer is a DummySigner — dummy signatures cannot
            produce valid creds; we refuse to even try.
        RuntimeError: if signer.is_ready() is False.
    """
    if isinstance(signer, DummySigner):
        raise RuntimeError(
            "polymarket_auth: dummy signer (DummySigner) cannot derive API "
            "credentials. Set SIGNER=private_key + PRIVATE_KEY to enable "
            "real derivation."
        )
    if not signer.is_ready():
        raise RuntimeError("polymarket_auth: signer is not ready — cannot derive creds")

    # Cache hit — return without touching the CLOB
    if CREDS_CACHE_PATH.exists():
        try:
            cached = json.loads(CREDS_CACHE_PATH.read_text(encoding="utf-8"))
            if all(k in cached for k in ("apiKey", "secret", "passphrase")):
                logger.info("polymarket_auth: loaded cached creds from %s", CREDS_CACHE_PATH)
                return cached
        except Exception as exc:
            logger.warning("polymarket_auth: cache read failed path=%s err=%s", CREDS_CACHE_PATH, exc)

    # Cache miss — derive via ClobClient. This requires the signer to produce
    # a valid EIP-712 signature; DummySigner would produce garbage. We've
    # already rejected dummy at the top of the function.
    logger.info("polymarket_auth: deriving new API creds via ClobClient")
    client = ClobClient(host=CLOB_HOST, chain_id=POLYGON_CHAIN_ID)  # Signer wiring deferred
    derived = client.create_or_derive_api_key()

    creds = {
        "apiKey": getattr(derived, "api_key", ""),
        "secret": getattr(derived, "api_secret", ""),
        "passphrase": getattr(derived, "api_passphrase", ""),
    }

    try:
        CREDS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CREDS_CACHE_PATH.write_text(json.dumps(creds, indent=2), encoding="utf-8")
        logger.info("polymarket_auth: cached creds to %s", CREDS_CACHE_PATH)
    except Exception as exc:
        logger.warning("polymarket_auth: cache write failed path=%s err=%s", CREDS_CACHE_PATH, exc)

    return creds
