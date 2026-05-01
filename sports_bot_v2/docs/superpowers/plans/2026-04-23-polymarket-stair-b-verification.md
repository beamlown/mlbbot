# Stair B Live Verification — 2026-04-24

## What was built

- **`core/ws_utils.py`** — shared `run_with_reconnect()` helper extracted from `market_stream.py`; 4 unit tests cover stop-on-event, reconnect counter, exception-swallow, and sleep-between-reconnects
- **`core/market_stream.py`** — `_run()` refactored to delegate to `ws_utils.run_with_reconnect`; zero behavior change; one strict improvement (faster stop-response — no spurious 3s sleep after stop signal)
- **`core/polymarket_auth.py`** — `provision_api_credentials(signer)` scaffold; raises `RuntimeError` containing "dummy" for DummySigner; derive-and-cache path via `py_clob_client.ClobClient.create_or_derive_api_key()`
- **`core/user_stream.py`** — `UserStreamClient` subscribes to `wss://ws-subscriptions-clob.polymarket.com/ws/user`; TRADE handler matches `maker_orders[].order_id` and calls `db.update_trade_fill`; ORDER handler logs status transitions; `debug_status()` surfaces counters
- **`core/db.py`** — widened partial unique index to `status IN ('open','pending')`, renamed `idx_trades_one_open_per_slug` → `idx_trades_one_live_per_slug` with idempotent DROP IF EXISTS migration; `fetch_open_trades` WHERE clause widened; new `update_trade_fill(order_id, actual_fill_px)` helper using SQLite `RETURNING id`; `_row_to_trade` now populates `actual_fill_px`
- **`bot_core.py`** — `UserStreamClient.start()` gated on `USER_STREAM_MIRROR=true` OR `PHASE=live`; three-layer safety net; `USER_STREAM_MIRROR` surfaced in `STARTUP_PROOF`
- **`.env.example`** — `USER_STREAM_MIRROR=false` documented with safety note

## Test suite

```
============================= 94 passed in 8.21s ==============================
```

Delta from Stair C closeout: +17 tests (77 → 94). All green. No regressions.

## Zero-connection grep

```
$ grep -rn "ws/user|ws-subscriptions-clob.polymarket.com/ws/user" \
    --include="*.py" core/ bot_core.py | grep -v test_ | grep -v "core/user_stream.py"

core/polymarket_auth.py:4:     # comment only (docstring reference)
bot_core.py:528:                # comment only (docstring reference)
```

**No actual connection code outside `core/user_stream.py`.** The two hits above are docstring/comment references, not `websocket.WebSocketApp(WS_URL)` calls.

## provision_api_credentials call sites

```
core/polymarket_auth.py:36: def provision_api_credentials(signer: Signer) -> dict[str, str]:  (definition)
core/user_stream.py:5:      # docstring reference
bot_core.py:533:            from core.polymarket_auth import provision_api_credentials  (lazy import, guarded)
bot_core.py:536:                creds = provision_api_credentials(get_signer())          (gated call)
```

Single call site, inside the `if USER_STREAM_MIRROR or _phase_is_live:` conditional. Default env never reaches it.

## Defaults proof

```
all Stair B defaults OK — no ws/user connection without explicit opt-in
```

Fresh Python process with all relevant env vars deleted: `USER_STREAM_MIRROR=False`, `thread_alive=False`, `connected=False`. Three safety gates engaged:
1. `USER_STREAM_MIRROR` parses false by default
2. `provision_api_credentials(DummySigner())` would raise (caught inner-except)
3. `UserStreamClient.start(api_creds=None)` no-ops

## Live bot status

**PID 9056** — unchanged since 2026-04-21 05:52 UTC. File edits only throughout Stair B; no running-process touches. Next organic respawn will:
- Apply idempotent `DROP INDEX idx_trades_one_open_per_slug` + new `CREATE UNIQUE INDEX idx_trades_one_live_per_slug`
- Pick up the widened `fetch_open_trades` WHERE clause (which now returns pending rows — currently zero in paper mode)
- Start market_stream via new `ws_utils.run_with_reconnect` path (zero behavior change)
- Log `"user_stream: disabled (default) — set USER_STREAM_MIRROR=true to enable"` and do nothing else user-stream-related

## Commits (Stair B)

1. `3fb07ff` — plan doc
2. `12c5f36` — Task 1: pending-row management (fetch + index + update_trade_fill)
3. `58c5543` — Task 2: ws_utils.run_with_reconnect helper
4. `b2aa3df` — Task 3: market_stream._run refactor
5. `f0f50a8` — Task 4: polymarket_auth scaffold
6. `21c55b7` — Task 5: UserStreamClient scaffold
7. `ae3ab1e` — Task 6: TRADE event handler + sqlite update
8. `e22039d` — Task 7: ORDER event handler regression test
9. `bb57afe` — Task 8: bot_core opt-in startup
10. `7cb299d` — Task 9: .env.example docs
11. `b3dbc23` — Task 9 follow-up: bot_core cosmetic fixes from Task 8 review

## Closes STILL_NEEDS_DONE_002 item #1 (Polymarket user/fill stream auth) — April 18 work unblocked.

Originally flagged `BLOCKED` on April 18 during the filetree-drift incident. The Stair B subsystem — `core/ws_utils.py`, `core/polymarket_auth.py`, `core/user_stream.py`, plus the `db.py` pending-row support — resolves the blocker cleanly. Prior quarantined `HANDOFF_RUNTIME_USER_STREAM_AUTH_UNBLOCK_001` contained only a 1-line presence check; zero code was salvaged. Stair B started clean and finished clean.

## Readiness statement

Stair B is dead code by default. With `USER_STREAM_MIRROR=true` + a real `PrivateKeySigner` (future production task) + credentials in `runtime/polymarket_creds.json`, the bot will:
1. Subscribe to `wss://.../ws/user` with derived API creds
2. Receive TRADE events and transition pending → open rows via `update_trade_fill`
3. Log ORDER events (new/matched/cancelled/expired) for audit

Today, with default env: no websocket opens, no auth derived, no creds file written. The paper bot at PID 9056 trades exactly as it did at the start of Stair B.

## Stair progress — the staircase

| Stair | Status | Key result |
|---|---|---|
| A (batch endpoints) | ✅ Shipped | 7× OB scan speedup (2.51s → 0.36s) |
| C (live_exec + kill-switches) | ✅ Shipped | Triple kill-switch; `PHASE=live` flip-ready |
| **B (user streaming)** | **✅ Shipped** | **ws/user subscription scaffold + TRADE/ORDER handlers; dead code by default** |
| D (account state sync) | Pending | `/positions`, `/trades`, balance on boot |

**Three of four stairs shipped.** Stair D remains for balance + drift reconciliation before a future live-trading flip.
