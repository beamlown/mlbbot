# Stair D Live Verification — 2026-04-24

## What was built

- **`core/polymarket_client.py`** — three new authenticated-GET helpers: `get_balance_allowance`, `get_my_trades`, `get_my_orders`. All wrap `py_clob_client.ClobClient` via the existing `retry_with_backoff`.
- **`core/account_sync.py`** — `reconcile_positions_on_boot()`, `fetch_balance()`, `sync_trades_history(since_ts)`. All three short-circuit to warn-and-noop when `_get_creds()` returns None (paper mode). Live mode: drift report from `orphan_local`/`orphan_server` comparison, low-balance warning, orphan-fill log on trade-history scan.
- **`bot_core.py`** — `reconcile_positions_on_boot()` + `fetch_balance()` called once after `init_db()`. Paper mode: two log lines ("no wallet, skipping"). Live mode: full reconcile report + balance check.
- **`.env.example`** — `MIN_BALANCE_WARN_USD` (default 50.0) and `ACCOUNT_SYNC_ENABLED` (default true) documented.

## Test suite

```
============================= 110 passed in 6.91s =============================
```

## Zero-unauth-call grep

```
(empty — exit 1 = no matches)
```

All `get_my_orders` / `get_my_trades` / `get_balance_allowance` callsites outside `core/polymarket_client.py` and `core/account_sync.py`: none.

## Paper-mode defaults proof

```
account_sync paper-mode defaults OK — no HTTP, no auth, no crash
```

With all of `PHASE`, `LIVE_TRADING_KILL_SWITCH`, `SIGNER`, `USER_STREAM_MIRROR`, `ACCOUNT_SYNC_ENABLED` unset, `reconcile_positions_on_boot()` and `fetch_balance()` return None; `sync_trades_history(0)` returns 0. No HTTP attempted, no auth derivation, no exception.

## Live bot status

```
ProcessId CreationDate
--------- ------------
     9056 4/21/2026 5:52:05 AM
```

PID 9056 unchanged since 2026-04-21 05:52 — Stair D code ships into the next respawn cycle without touching the running paper bot.

## Commits (Stair D)

1. `5aa59be` — plan doc
2. `965b55a` — Task 1: authenticated GET helpers
3. `0864683` — Task 2: account_sync scaffold (no-op paper mode)
4. `035a1f5` — Task 3: reconcile drift detection
5. `9c388e7` — Task 4: fetch_balance + low-balance warn
6. `6cc6497` — Task 5: sync_trades_history orphan-fill detection
7. `(this commit)` — Task 6: bot_core integration + env docs + verification

## Readiness statement

Stair D completes the Polymarket staircase. **Four of four stairs shipped**:

| Stair | Status | Key result |
|---|---|---|
| A — batch reads | ✅ | 7× OB scan speedup |
| C — execution writes + kill-switches | ✅ | Triple kill-switch, `PHASE=live` flip-ready |
| B — user streaming | ✅ | TRADE events drive pending→open transitions |
| D — account state sync | ✅ | Boot-time drift + balance + trade-history sync |

The bot still trades paper by default. To go live: flip `PHASE=live`, `LIVE_TRADING_KILL_SWITCH=false`, `USER_STREAM_MIRROR=true`, `SIGNER=private_key`, set `PRIVATE_KEY`, fund wallet, run the operator pre-flip checklist. All code paths are in place.
