"""
core/signer.py — Order signing protocol + implementations.

This module owns the abstraction boundary between "building an order request"
(public, not sensitive) and "producing a cryptographic signature" (private,
requires a wallet key). Three things live here:

1. `OrderArgs` — pre-sign request dataclass. No crypto.
2. `SignedOrder` — post-sign opaque blob. Real instances carry an EIP-712
   signature py_clob_client can submit; dummy instances carry a traceable fake
   string that will NEVER be accepted by the CLOB.
3. `Signer` — protocol. Two implementations:
   - `DummySigner`: returns traceable fake signatures; is_ready=False so
     live_exec refuses to submit them.
   - `PrivateKeySigner`: fails loudly at __init__ if PRIVATE_KEY env is unset;
     sign_order() is a placeholder (NotImplementedError) for this cycle.
     Real crypto wiring lands in a future Stair C production task.

Why: Stair C builds the code paths "one env-flag flip" away from real live
trading but never activates them. DummySigner lets unit tests exercise every
path WITHOUT ever constructing a real signature.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Literal, Protocol

SideT = Literal["BUY", "SELL"]
OrderTypeT = Literal["GTC", "FOK", "GTD"]
_VALID_SIDES: frozenset[str] = frozenset({"BUY", "SELL"})


@dataclass
class OrderArgs:
    """Pre-signature order request. Pure data — no crypto."""
    token_id: str
    side: SideT
    price: float
    size: float  # USDC notional
    order_type: OrderTypeT = "GTC"

    def __post_init__(self) -> None:
        if self.side not in _VALID_SIDES:
            raise ValueError(f"OrderArgs.side must be BUY or SELL, got {self.side!r}")


@dataclass
class SignedOrder:
    """Post-signature opaque payload. Real instances carry an EIP-712 sig that
    py_clob_client can submit; dummy instances carry a traceable fake."""
    blob: str
    args: OrderArgs
    signer_tag: str  # "dummy:<hex>" or "pk:<0x-addr-prefix>"

    @property
    def is_dummy(self) -> bool:
        return self.signer_tag.startswith("dummy:")


class Signer(Protocol):
    def sign_order(self, args: OrderArgs) -> SignedOrder: ...
    def is_ready(self) -> bool: ...


class DummySigner:
    """Returns structurally-valid fake signatures for build/test paths.
    CLOB will reject them — is_ready() returns False so live_exec never submits."""

    def sign_order(self, args: OrderArgs) -> SignedOrder:
        tag = f"dummy:{uuid.uuid4().hex[:8]}"
        return SignedOrder(
            blob=f"dummy:{uuid.uuid4().hex}",
            args=args,
            signer_tag=tag,
        )

    def is_ready(self) -> bool:
        return False


class PrivateKeySigner:
    """Signs orders using PRIVATE_KEY env var via eth-account / py_clob_client.

    Constructor raises if PRIVATE_KEY is unset — fail-loud, never silently
    fall back. sign_order() is intentionally NotImplementedError this cycle
    so nobody accidentally wires real signing without completing the production
    Stair C task (which must also verify wallet funding, rate limits, and
    add a kill-switch test with live CLOB).
    """

    def __init__(self) -> None:
        key = os.getenv("PRIVATE_KEY", "").strip()
        if not key:
            raise RuntimeError(
                "PrivateKeySigner: PRIVATE_KEY env var is required. "
                "If you're not ready to go live, use SIGNER=dummy instead."
            )
        self._key = key

    def sign_order(self, args: OrderArgs) -> SignedOrder:
        raise NotImplementedError(
            "Real crypto signing deferred. This code path exists to keep the "
            "structural flip-to-live possible in a future task."
        )

    def is_ready(self) -> bool:
        return True


def get_signer() -> Signer:
    """Factory reads SIGNER env var. Defaults to 'dummy' so nothing ever
    risks submitting a real signature without explicit opt-in."""
    name = os.getenv("SIGNER", "dummy").strip().lower()
    if name == "dummy":
        return DummySigner()
    if name == "private_key":
        return PrivateKeySigner()
    raise ValueError(f"Unknown SIGNER={name!r}; expected 'dummy' or 'private_key'")
