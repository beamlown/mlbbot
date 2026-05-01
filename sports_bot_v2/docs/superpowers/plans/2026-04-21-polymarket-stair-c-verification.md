# Stair C Live Verification — 2026-04-23

## What was built

- **`core/signer.py`** — `OrderArgs`, `SignedOrder`, `Signer` protocol, `DummySigner` (is_ready=False), `PrivateKeySigner` (fail-loud on missing `PRIVATE_KEY`, `sign_order()` raises NotImplementedError until a future production task), `get_signer()` factory with `dummy` default
- **`core/live_exec.py`** — `place_order`, `cancel_order`, `cancel_all` guarded by TRIPLE kill-switch:
  1. `PHASE == "live"` (default `"paper"`)
  2. `LIVE_TRADING_KILL_SWITCH` OFF via fail-safe-whitelist-of-OFF-values parse (default `"true"` → engaged)
  3. `signer.is_ready() == True` (default DummySigner → False)
  Plus tick-grid snap via `polymarket_client.tick_size`, price-out-of-band rejection, and full exception capture (sign + submit both wrapped in try/except returning `status="error"`)
- **`core/paper_exec.py::open_position`** — branches on PHASE. Paper path BYTE-FOR-BYTE UNCHANGED. Live path routes through `live_exec.place_order`, sets `status="pending"` + `order_id` on placed; returns `None` on reject/error so caller skips DB insert
- **`core/db.py`** — idempotent `order_id TEXT` migration; `insert_open_trade` now respects `trade.status` instead of hardcoding `"open"`
- **`core/types.py`** — `Trade.order_id: str | None = None`
- **`bot_core.py:937`** — the one `open_position` caller handles `Trade | None` return with logger.info + `continue`
- **`core/polymarket_client.py`** — preflight: `_save_tick_cache` now serialized by `threading.Lock` + atomic temp-write-then-replace
- **`.env.example`** — documented all four new vars with 5-step pre-flip operator checklist

## Test suite

```
============================= 77 passed in 5.58s ==============================
```

**Delta from Stair A closeout:** +38 tests (was 39 → now 77). All green.

## Zero-live-call grep proof

```
$ grep -rn "post_order|cancel_orders|cancel_market_orders|create_and_post_order" \
    --include="*.py" core/ bot_core.py | grep -v test_ | grep -v "core/live_exec.py"
(empty)
```

**Verdict:** No module outside `core/live_exec.py` reaches a py_clob_client write endpoint. Kill-switch surface is the ONLY place in the code that can talk to the CLOB for order placement. Verified.

## Defaults proof

```
signer OK
live_exec OK  PHASE=paper KILL_SWITCH=True
paper_exec OK  PHASE=paper
defaults OK — nothing goes live without explicit env change
```

Fresh import into a clean Python process with no env overrides: all three gates are ENGAGED by default. Real money is protected by three independent safeguards that must ALL be disengaged for an order to leave the box.

## bot_core syntax check

`bot_core.py OK` (parses cleanly under Python 3.14).

## Live verification

- **Bot PID at plan start:** 9056, running `USE_BATCH_PRICES=true` from Stair A
- **Bot restart during Stair C:** NOT REQUIRED. All Stair C changes are dead code at default PHASE=paper + LIVE_TRADING_KILL_SWITCH=true.
- **Bot PID after Task 11 verification:** **STILL 9056** (unchanged since 4/21 05:52). Zero touches to the running process — only file edits on disk.
- **Side-effect at next organic respawn:** `init_db()` will run the idempotent `ALTER TABLE trades ADD COLUMN order_id TEXT` migration. Existing rows get `order_id=NULL`. No other behavioral change on the paper path.

## Commits (Stair C)

1. `b458f86` — atomic + thread-safe tick-cache writes (preflight, closes task #26)
2. `e7c061d` — trades.order_id column migration (idempotent ALTER)
3. `3a03437` — Trade.order_id field + db insert/select/fetch support
4. `bce2300` — signer.py scaffold (OrderArgs, SignedOrder, Signer protocol, DummySigner)
5. `3a75251` — PrivateKeySigner + get_signer factory
6. `a71ca5b` — live_exec.place_order with dual-gate kill-switches (initial)
7. `75f29a0` — live_exec fail-safe kill-switch parse (review followup #1)
8. `4d95833` — live_exec wrap sign_order in error-contract try/except (review followup #2)
9. `81816c9` — lock in tick-snap and price-band tests (Task 7)
10. `744544e` — cancel_order + cancel_all (Task 8)
11. `17c52ca` — paper_exec PHASE branch + insert_open_trade status fix + bot_core caller (Task 9)
12. `4663f14` — strengthen paper-path regression test + guard live_order_id=None render (Task 9 review followup)
13. `fe70ee0` — .env.example Stair C docs (Task 10)

**13 commits total.** Task 6 received 3 review iterations (initial + 2 safety fixes); Task 9 received 2 (initial + review followup). All other tasks landed clean on first pass.

## Open items (tracked, not blocking Stair C)

- **Task #38** — *Stair C closeout: pending-row management (uniqueness + fetch)*. Before PHASE=live flip, `insert_open_trade`'s duplicate check and `fetch_open_trades` WHERE clause need to treat `status IN ('open', 'pending')` instead of just `'open'`. Otherwise a pending live order can be invisible to bot management. Stair B's user_stream will provide the pending→open transition.
- **`PrivateKeySigner.sign_order()` is `NotImplementedError`** — intentional. A future production-Stair-C task wires it via py_clob_client + eth_account, with its own wallet-funding verification and a live-CLOB $1-probe test.

## Readiness statement

Stair C's dead code is in place, tested, reviewed, and shipped. Flipping `PHASE=live` today is still blocked by three independent safeguards (env parse failures all engage the switch; default signer refuses submit) so no real money can leak. Flipping to live requires completing the 5-step operator checklist documented in `.env.example` AND the future `PrivateKeySigner.sign_order()` implementation.

**The bot trades paper at PID 9056 exactly as it did before this work.**
