# Polymarket Full Integration Staircase — Design Spec

**Date:** 2026-04-20
**Target bot:** `C:\Users\johnny\Desktop\sports_bot_v2` (paper-mode MLB; Polymarket CLOB)
**Decision engine:** `C:\Users\johnny\Desktop\mlb_model`
**Driving goal:** Give the bot a complete, typed, resilient surface against every Polymarket API it needs — first to tighten paper-trading fidelity, then to be one env-flag flip from live execution.

## Frame

The bot currently uses 5 Polymarket endpoints (`gamma-api/events`, `gamma-api/markets`, `gamma-api/orderbook`, `clob/book`, `ws/market`) and is missing 15+ more. The market websocket was activated on 2026-04-20 and is now receiving live `price_change` events at 100% parse-hit. The bot has `py_clob_client 0.34.6` and the full `eth-*` signing stack installed but zero imports or usage — wallet/execution deps were prepped in an earlier session and never wired.

Operator priority: **prove the bot trades winners in paper first, then flip to live.** This design therefore organizes the work into a four-stair staircase where live-execution code is fully built and tested but never activated in this cycle.

## Prior work context

This spec is **Phase P3** of the umbrella plan in `2026-04-18-trading-bot-improvements-design.md`. It is not a new track — it resolves work that was explicitly deferred on April 18 and items still open on the April-18 operator punch list.

**Built on top of (already done):**
- P0 Attribution spine — DB columns `entry_model_prob`, `actual_fill_px`, `exit_reason`, `trade_class`, etc. are in place (`trades_sports.db`). Stair B's TRADE event handler writes to these fields directly.
- P1 Paper slippage model — `core/paper_exec.py::_walk_the_book` is live; the paper → live swap in Stair C preserves the same fill-estimation call-site.
- Market stream (activated 2026-04-20) — `core/market_stream.py` + `core/state_hub.py`; Stair B extracts the shared reconnect loop into `core/ws_utils.py` and `user_stream.py` reuses the same pattern.

**Prior related work still open (this spec closes):**
- `STILL_NEEDS_DONE_002.md` item #1 *"Unblock Polymarket user/fill stream auth"* (BLOCKED since April 18) → **resolved by Stair B**.
- `STILL_NEEDS_DONE_002.md` item #2 *"Finish final authority separation"* — unchanged; `mlb_model` stays decision authority, `sports_bot_v2` takes on execution writes too. `mlb_model/core/execution_guard.py` is not created by this spec — it remains a placeholder for any future execution-side validation the model wants to enforce.

**Prior quarantined attempts (not salvageable, documented for audit):**
- `HANDOFF_RUNTIME_USER_STREAM_AUTH_UNBLOCK_001` (April 18) — single-line presence check, quarantined by filetree-drift incident. **No code was written.** Stair B starts clean.
- `HANDOFF_REALTIME_MARKET_EXECUTION_DISCOVERY_001` — was about market *discovery* (not order execution); orthogonal to this spec; already superseded by working `core/discovery.py`.
- `HANDOFF_EXECUTION_CONTRACT_BIND_001` + `*_HELD_SIDE_SEMANTICS_001` + `*_METADATA_PERSISTENCE_PROOF_001` — all attribution-field work, landed earlier as part of P0.

**Touches existing files (not new files only):**
- `core/paper_exec.py` — branches on `PHASE` to delegate to `live_exec.py`
- `core/orderbook.py` — opt-in to batch endpoints via feature flag
- `core/market_stream.py` — consumes tick-size cache
- `bot_core.py` — starts `user_stream` client and calls `account_sync` on boot
- `launch_all.py` — unchanged (no new launcher children; user_stream runs in-process)

## Out of scope

- Flipping `PHASE=live` or running real orders against mainnet CLOB during this cycle.
- Data API historic endpoints (`/prices-history`, `/trades`, `/volumes`, `/activities`) — deferred to a future backtesting-harness project.
- Incentivized-markets / rewards API — not used by current strategy.
- Wallet provisioning / private-key management — spec uses a `DummySigner` interface so no real key is ever loaded during development.
- Non-MLB sports (basketball path already exists; Polymarket client is sport-agnostic and will serve both).
- Gamma events re-architecture — existing discovery works fine at 182 markets/loop.

## Scope locks (from brainstorm)

| Dimension | Locked value |
|---|---|
| Approach | **Approach 1** — strict linear staircase; each stair ships and is observed before next starts |
| Stair A depth | **A-Slim** — batch CLOB endpoints (`/midpoints`, `/prices`, `/spreads`, `/last-trade-price`) + `/tick-size` only; no Data API |
| Stair C depth | **C1** — ready-to-flip; code exists and is tested; PHASE=live never set this cycle; kill-switch env var as second gate |
| Wallet / auth | **W3** — `Signer` protocol with `DummySigner` fake implementation; real `PrivateKeySigner` left as named follow-up |

## Staircase order

**A → C → B → D**, revised from the naive A→B→C→D. Rationale: user-ws events (B) only fire when the bot submits orders (C). Building B before C yields a dormant subscriber with nothing to parse. Resilience (E) is not its own stair — it is folded into each stair as we touch new endpoints.

---

## Architecture

New modules in `core/`, plus surgical edits to existing files:

```
sports_bot_v2/core/
  polymarket_client.py   [NEW]  typed HTTP facade; batch endpoints; 429-aware
  signer.py              [NEW]  Signer protocol + DummySigner (+ PrivateKeySigner later)
  live_exec.py           [NEW]  place/cancel/cancel_all; kill-switch gated
  user_stream.py         [NEW]  ws/user channel → TRADE/ORDER events → sqlite
  account_sync.py        [NEW]  positions/balance/trades reconcile on boot
  ws_utils.py            [NEW]  shared ws reconnect loop (extracted from market_stream)
  paper_exec.py          [edit] delegate to live_exec when PHASE=live
  orderbook.py           [edit] use batch /midpoints instead of 180 parallel GETs (feature-flagged)
  market_stream.py       [edit] consume tick-size when snapping mid prices
```

`polymarket_client.py` is the hub. All four stairs sit on it. It owns: base URLs, auth-header injection, rate-limit accounting, 429 `Retry-After` handling, typed response models (`TypedDict`). No other module talks to `clob.polymarket.com` directly; every HTTP call routes through this facade.

---

## Component design — one subsection per stair

### Stair A — A-Slim data reads (~400 LoC)

**Purpose:** Replace the per-loop 180-parallel-HTTP fanout with batched endpoints; unblock C1's tick-grid requirement.

**Public API (in `polymarket_client.py`):**

```python
def batch_midpoints(token_ids: list[str]) -> dict[str, float]
def batch_prices(token_ids: list[str], side: Literal["BUY","SELL"]) -> dict[str, float]
def batch_spreads(token_ids: list[str]) -> dict[str, float]
def last_trade_price(token_id: str) -> tuple[float, int]  # price, ts
def tick_size(token_id: str) -> float   # cached
```

**Wire points:**
- `bot_core.py` OB scan loop: when `USE_BATCH_PRICES=true`, collect all live-market token_ids, call `batch_midpoints` + `batch_prices(side="SELL")` once per loop instead of 180 parallel `/book` calls. Keeps full `/book` walk for the one market we're about to trade on (book-walk still needed for VWAP fill estimation).
- `market_stream.py::_on_message`: when updating `state_hub.update_mark`, snap `current_price` to tick grid using `tick_size(asset_id)` cache.
- Tick-size registry written to `runtime/tick_sizes.json`, refreshed on market discovery (every 20 loops).

**Resilience:** extend `core/utils.retry_with_backoff` to read `Retry-After` header on 429 responses; used by every `polymarket_client` call. Per-endpoint budget counters logged every 100 loops.

### Stair C — C1 execution writes (~600 LoC)

**Purpose:** Build signed-order placement, cancellation, and panic stop — gated behind two independent flags so real money is impossible this cycle.

**Public API:**

```python
# signer.py
class Signer(Protocol):
    def sign_order(self, args: OrderArgs) -> SignedOrder: ...

class DummySigner:
    def sign_order(self, args): return SignedOrder(blob=f"dummy:{uuid()}", ...)

# live_exec.py
def place_order(side, token_id, price, size_usd) -> OrderResult
def cancel_order(order_id) -> CancelResult
def cancel_all() -> CancelAllResult   # panic stop
```

**Gating (both must flip for a real order to leave the box):**
- `PHASE=paper` (default) vs `PHASE=live` — this spec never sets `live`
- `LIVE_TRADING_KILL_SWITCH=true` (default) vs `false` — second independent gate

`paper_exec.open_position` branches on `PHASE`:
- `paper`: walk the book locally, insert sqlite row immediately with `status='open'` (current behavior, unchanged)
- `live`: call `live_exec.place_order()`; on success insert sqlite row with `status='pending'` and real `order_id`; row transitions to `status='open'` when `user_stream` delivers the matching TRADE event (Stair B)

**Tick-grid enforcement:** `live_exec.place_order` calls `polymarket_client.tick_size(token_id)` and snaps price via `round(price / tick) * tick`. Prices that would snap to `<0.01` or `>0.99` reject with reason `"price_out_of_band"`.

**DummySigner tracing:** every `dummy:{uuid}` blob gets logged at INFO with full OrderArgs payload so tests can assert correct signing calls even without real crypto.

### Stair B — User streaming (~300 LoC)

**Purpose:** Mirror the market-ws pattern for the user channel so paper-fill-equivalent events populate sqlite in realtime; sets up the same infrastructure that will handle real fills when `PHASE=live`.

**Public API:**

```python
# user_stream.py
class UserStreamClient:
    def start(self, api_creds: ApiCreds) -> None
    def stop(self) -> None
    def debug_status(self) -> dict
```

**Shared infrastructure:** extract the reconnect + ping loop from `market_stream.py` into `ws_utils.run_with_reconnect(...)`; both streams use it.

**Event handlers:**
- TRADE event → `db.update_trade_fill(order_id, actual_fill_px, fill_size, fill_ts)`; also bumps `status` from `pending` → `open`.
- ORDER event → log transition; on `matched` or `cancelled` update sqlite accordingly.

**Activation:** connects only when `PHASE=live` OR `USER_STREAM_MIRROR=true`. The mirror flag exists so the dashboard can show "what would a real fill look like" in paper mode once Stair D ships — but is off by default this cycle.

### Stair D — Account state sync (~200 LoC)

**Purpose:** Reconcile local sqlite state with CLOB server state on boot; fetch balance for position-sizing sanity.

**Public API:**

```python
# account_sync.py
def reconcile_positions_on_boot() -> ReconcileReport
def fetch_balance() -> float   # USDC
def sync_trades_history(since_ts: int) -> int   # rows inserted
```

**Boot sequence** (added to `bot_core.main()` after `init_db()`):
1. If `PHASE=paper` and no API creds set: log `"account_sync: paper mode, no wallet, skipping"` and return.
2. Fetch `/positions`, compare with `fetch_open_trades()`. Log drift (either direction).
3. Fetch balance; if `balance < MAX_POSITION_SIZE_USD * MAX_CONCURRENT_TRADES`, warn.
4. Sync last 72h of trades history into sqlite (idempotent via `order_id` primary key).

---

## Data flow — the key invariant

```
tradable signal
  ↓
model_bridge.get_approved_intents()
  ↓
bot_core check_entry_gates
  ↓
paper_exec.open_position(..., mode=CURRENT_PHASE)
    │
    ├── mode=paper:  walk book locally, insert sqlite row status='open'     [current behavior]
    │
    └── mode=live:   live_exec.place_order()
                       ↓
                     signer.sign_order()
                       ↓
                     POST /order → returns order_id
                       ↓
                     sqlite row inserted status='pending'
                       ↓ (async, via user_stream)
                     TRADE event → sqlite row updated: actual_fill_px, status='open'
```

In this cycle: **only the `paper` branch is ever exercised.** The `live` branch compiles, type-checks, passes unit tests against `DummySigner`, but is gated behind two independent flags (`PHASE=live` + `LIVE_TRADING_KILL_SWITCH=false`) that we never set.

---

## Error handling

| Failure | Handler | Surface |
|---|---|---|
| HTTP 429 | `retry_with_backoff` reads `Retry-After`, sleeps, retries | log at INFO |
| HTTP 5xx | exponential backoff, up to 3 attempts | log at WARN; caller sees None |
| ws disconnect | `ws_utils.run_with_reconnect` — exponential, max 30s | log at WARN with reconnect count |
| Order rejected by CLOB | `live_exec` logs full reject; **no sqlite row** inserted | log at WARN; dashboard shows reject reasons |
| Signer missing real key | `PrivateKeySigner.__init__` raises if `PRIVATE_KEY` env empty | process exits at boot; fail-loud |
| Tick-size unknown for market | snap to conservative `0.001`; warn once per market | INFO on use; refresh on next discovery |
| Kill-switch engaged | `live_exec.place_order` returns `{status:"rejected", reason:"kill_switch"}` | WARN on every attempt |
| User-ws message for unknown order | log, drop | DEBUG (high volume) |
| `/positions` returns drift | log diff; do not auto-reconcile; require human to resolve | WARN |

---

## Testing

### Unit tests (merge-blocking)

| Test | What it proves |
|---|---|
| `DummySigner.sign_order` returns expected shape | Signer protocol contract |
| `live_exec.place_order` with DummySigner | Correct OrderArgs built, tick snapping, kill-switch hard-return, PHASE=paper no-op |
| `polymarket_client.batch_midpoints` with recorded response | Parses real response shape, handles empty list |
| `polymarket_client.tick_size` cache behavior | Fetches once, serves from cache, refreshes on miss |
| `user_stream` parser — TRADE event | Updates sqlite `actual_fill_px`, status transition |
| `user_stream` parser — ORDER event | Correct status progression `pending`→`matched`→`open` |
| `account_sync.reconcile_positions_on_boot` | Drift-absent, drift-present, empty-positions, no-creds cases |
| `retry_with_backoff` 429 path | Reads `Retry-After`, sleeps correct duration |

### Integration tests (smoke; not merge-blocking)

- Live hit to `clob.polymarket.com/tick-size?token_id=<known_bal-kc_yes_token>` — asserts non-empty, asserts tick ∈ {0.01, 0.001}.
- Replay a captured `ws/user` message sequence through parser — bit-for-bit sqlite equivalence.
- 30-min full-loop run with `PHASE=paper`, `LIVE_TRADING_KILL_SWITCH=true` — grep logs for zero `POST /order` calls; assert zero real orders submitted.

### Pre-flip human checklist (out-of-scope for this cycle; documented as follow-up)

Before any future switch to `PHASE=live` + `LIVE_TRADING_KILL_SWITCH=false`:

1. Balance check: confirm USDC balance ≥ `MAX_POSITION_SIZE_USD * MAX_CONCURRENT_TRADES * 2`.
2. Kill-switch test: set `PHASE=live` but keep `KILL_SWITCH=true`; verify every paper trade's would-be live call is blocked.
3. DummySigner → PrivateKeySigner swap: private key loaded from `.env.secrets` (gitignored).
4. 10-order probe: `MAX_POSITION_SIZE_USD=1.00`, one trading day, monitor every fill.
5. Dashboard parity: confirm `trades_sports.db` rows match Polymarket account activity tab.

---

## Rollout

| Stair | Merge criterion | Observation window |
|---|---|---|
| **A** | Unit tests green; 30-min paper run shows `batch_midpoints` replacing fanout; `tick_sizes.json` populated | 2–5 days of paper runs |
| **C** | Unit tests green; grep confirms zero live calls; kill-switch path verified via mocked PHASE=live | No live observation; code sits gated |
| **B** | Unit tests green; replay of captured ws/user fixture produces correct sqlite state; paper-mirror mode disabled | No live observation (no live fills to receive) |
| **D** | Unit tests green; boot reconcile logs run correctly in paper mode (skip + log); mock test for drift paths | No live observation |

Each stair gets its own implementation-plan cycle via `writing-plans`. This spec commits to the staircase and the design; the actual step-by-step tasks for Stair A will be generated by the next `writing-plans` invocation.

---

## Open questions (tracked for follow-up; do not block spec approval)

1. **Gamma vs CLOB market metadata precedence**: current discovery uses Gamma; some endpoints (`/tick-size`) are CLOB-only. Resolved by having `polymarket_client` own that routing — but unresolved: if Gamma and CLOB disagree about a market's outcome tokens, whose truth wins? (Default: CLOB for execution-critical fields, Gamma for display metadata.)
2. **Paper-mirror mode for Stair B**: should we add a `USER_STREAM_MIRROR=true` path that injects synthetic TRADE events when paper trades fill locally, so the downstream DB+dashboard code exercises the same code path? (Probably yes, but deferred — belongs to Stair B plan, not this design.)
3. **Rate-limit budget values**: Polymarket docs list rate limits per endpoint. We'll set conservative budgets when we instrument `polymarket_client`; exact numbers TBD from docs at plan-writing time.
4. **API key rotation**: `py_clob_client.create_or_derive_api_key()` returns durable creds. Rotation cadence is a Stair C plan concern, not this design.

---

## Success criteria

This design is successful if, after all four stairs ship:

1. The bot's realtime decision loop uses batched price endpoints — verified by log line `"OB_SCAN: batch_midpoints n=180 elapsed<0.5s"`.
2. A developer can read `live_exec.py` and a complete order lifecycle is visible end-to-end without touching external docs.
3. Setting `PHASE=live` + `LIVE_TRADING_KILL_SWITCH=false` + `SIGNER=PrivateKeySigner` + a funded wallet is the *only* change needed to place real orders — no additional code is required at the call site.
4. On process restart, `account_sync` logs a clean reconcile report whether in paper or live mode.
5. All unit tests pass on Windows 11 / Python 3.14 with zero network access.
