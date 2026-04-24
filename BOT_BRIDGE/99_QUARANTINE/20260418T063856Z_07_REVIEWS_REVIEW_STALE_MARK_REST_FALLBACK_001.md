# REVIEW_STALE_MARK_REST_FALLBACK_001

Decision: **APPROVED**

Date: 2026-04-09

---

## Scope

Single file: `dashboard_server.py`. Confirmed by `git show --stat b31b548`: 1 file changed. No edits to `market_stream.py`, `state_hub.py`, or any other file.

---

## Implementation verified (static)

| Check | Line(s) | Status |
|---|---|---|
| `CLOB_BOOK` constant | 57 | ✓ `https://clob.polymarket.com/book` |
| `STALE_REST_POLL_SEC = 30.0` | 58 | ✓ |
| `STALE_REST_THROTTLE_SEC = 20.0` | 59 | ✓ |
| `_rest_poll_ts: dict[str, float] = {}` | 60 | ✓ |
| `_rest_poll_lock = threading.Lock()` | 61 | ✓ |
| `_poll_stale_mark()` defined before `_stream_positions_mark()` | 394–420 | ✓ |
| CLOB endpoint uses `token_id` param | 397 | ✓ `f"{CLOB_BOOK}?token_id={asset_id}"` |
| `best_bid = bids[0]["price"]`, `best_ask = asks[0]["price"]` | 401–402 | ✓ matches `orderbook.py` pattern |
| `current_price = best_bid if best_bid is not None else best_ask` | 403 | ✓ matches stream priority |
| `update_mark(..., source="rest_fallback")` | 406–415 | ✓ all required kwargs present |
| `[STALE_POLL]` log on success and warning on empty book | 416–418 | ✓ |
| Exception caught, logged as warning (no crash) | 419–420 | ✓ |
| Lock acquired briefly for timestamp claim only | 437–444 | ✓ HTTP calls outside lock |
| `_rest_poll_ts[_slug] = _now_ts` set before releasing lock | 443 | ✓ prevents duplicate concurrent polls |
| REST fallback block inserted between `snapshot()` and `_fetch_trades()` | 432–448 | ✓ |
| Re-snapshot only fires when `_to_poll` non-empty | 447–448 | ✓ no unnecessary re-snapshot |
| `py_compile` passed | — | ✓ confirmed by worker |

---

## Logic correctness

- `_mark_age` when no mark exists: `_now_ts - float(None or 0) = _now_ts` (~1.7B) → always > 30 → poll fires immediately on first SSE tick. Correct.
- Throttle: once polled, `_rest_poll_ts[slug] = now` → next check `(now - last_poll) > 20` prevents re-poll for 20s. Correct.
- Lock scope: only the timestamp dict read/write is inside the lock. `_poll_stale_mark()` runs outside. Multiple concurrent SSE connections won't deadlock waiting on an HTTP call. Correct.
- Re-snapshot after polls: gives the injected mark a chance to appear in the positions payload on the same SSE tick. Correct.

---

## Runtime verification

Not completed in this pass (task forbids process restart). Required before SMOKE_003:

1. Operator restarts dashboard process (`python dashboard_server.py` from `sports_bot_v2/`)
2. Wait ≤30s → `[STALE_POLL]` log line should appear
3. SSE `/api/stream/state` should show `mark_source=rest_fallback`, `stale=false`, non-null `current_price`

---

## Rollback

Revert commit `b31b548` or manually remove: module-level constants (lines 57–61), `_poll_stale_mark()` (lines 394–420), and the REST fallback block (lines 433–448) from `_stream_positions_mark()`.

---

## Commit

`b31b548` — `Add dashboard stale mark REST fallback`
