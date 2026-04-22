# Trading Bot Improvements — Design Spec

**Date:** 2026-04-18
**Target bot:** `C:\Users\johnny\Desktop\sports_bot_v2` (live paper, Polymarket MLB)
**Decision engine:** `C:\Users\johnny\Desktop\mlb_model`
**Work-order bridge:** `C:\Users\johnny\Desktop\BOT_BRIDGE`

## Frame

Operator selected pillars **A (edge/profitability)**, **C (execution quality)**, **E (observability)**.
Bot is in **paper-only** mode; horizon is **B+C** — maximize learning velocity and prove the model has real edge before graduating to real money.

The core need is a **trustworthy feedback loop**. Without clean attribution, more trades and more dashboards don't help; with it, every session becomes a measurement.

## Out of scope

- ~~Real-money execution wiring~~ → **moved into new Phase P3** (added 2026-04-21; kill-switch-gated build, never called live this cycle). See `2026-04-20-polymarket-integration-design.md`.
- Model architecture changes (model foundation work is already in-flight via separate tracks)
- New sports (NBA, NFL) — MLB only
- Sizing/bankroll logic overhaul (separate tasks already exist in bridge)
- Data hydration — already being handled (`TASK_MLB_*` handoffs in-flight)

## Approach

Three ordered phases, each a set of small BOT_BRIDGE work orders.

### Phase P0 — Attribution spine (foundation; nothing else works without this)

Every paper trade must produce a complete audit record so we can answer: **did the model get this right or wrong, and if wrong, was it the model or execution?**

Fields captured per trade:
- `entry_model_prob` — model's win probability at fill
- `entry_market_prob` — market-implied probability at fill
- `expected_edge_pct` — (model - market)
- `actual_fill_px`, `actual_fill_size`
- `exit_reason` — enum: `TP | SL | RESOLUTION | MANUAL | SESSION_CAP | COOLDOWN`
- `exit_model_prob`, `exit_market_prob`
- `hold_seconds`
- `resolved_winner` — side that won (when resolved)
- `model_side_was_right` — bool
- `realized_pnl`
- `trade_class` — enum: `MODEL_WIN_EXPECTED | MODEL_WIN_LUCKY | MODEL_LOSS_EXPECTED | MODEL_LOSS_EXECUTION | UNRESOLVED`

Work orders:
1. **TRADE_ATTRIBUTION_SCHEMA_001** — DB schema + JSONL writer
2. **TRADE_ATTRIBUTION_WIRING_001** — wire entry/exit/resolution paths to populate fields; backfill existing trades where possible
3. **ATTRIBUTION_DASHBOARD_001** — dashboard panels: calibration curve, edge-realization scatter, hit-rate by confidence bucket, trade_class breakdown

### Phase P1 — Targeted execution/observability fixes

Only the items that would otherwise corrupt P0 attribution data or mislead the operator. Not a full sweep.

Work orders:
4. **SHADOW_ENGINE_RENAME_001** — `shadow_engine` in launcher is actually `mlb_model/integration/recommendation_api`. Rename to `mlb_recommendation_api` across launcher, log file, docs, dashboard. Legacy name causes operator confusion.
5. **PAPER_SLIPPAGE_MODEL_001** — paper fills currently assume ideal (mid / best). Add orderbook-walking slippage model so paper fills match what real-money would actually get. Toggleable; results logged to attribution record.
6. **DB_TRUTH_SINGLE_SOURCE_001** — audit every dashboard panel: everything reads from `trades_sports.db` as authority. Flag any in-memory / computed-on-the-fly values. Closes the loop on mark-source work already done.
7. **REGISTRY_PREGAME_WINDOW_001** — MLB registry currently holds today only, causing future-dated Polymarket events (e.g. `mlb-bal-kc-2026-04-20`) to log as `no_registry_match` on 2026-04-18. Decide: expand window to N days, OR classify future-day events explicitly as `future_scheduled`. Kills log noise.

### Phase P2 — Replay harness (velocity multiplier; depends on P0 data quality)

Once attribution data is clean, we can re-run historical discoveries against arbitrary configs without waiting for more live sessions.

Work orders:
8. **REPLAY_INPUT_CAPTURE_001** — ensure per-loop snapshot (orderbook, mark, model inputs, timestamp) is durable in `runtime/ob_snapshots/` with schema compatible with replay.
9. **REPLAY_HARNESS_BUILD_001** — build/revive harness: date range + config (confidence gate, edge threshold, sizing) → counterfactual trade set + attribution summary.
10. **REPLAY_SWEEP_CLI_001** — CLI: `python replay.py --start YYYY-MM-DD --end YYYY-MM-DD --config configs/*.yaml` outputs win rate, Brier score, calibration, expected-vs-actual PnL per config.

### Phase P3 — Polymarket full integration staircase (added 2026-04-21)

Builds on top of P0 attribution + P1 paper slippage. Takes the bot from "paper-only" to "one-env-flag-flip from live" by wiring every Polymarket API the bot needs behind a double-gated kill-switch. **No real money is risked in this phase.** Resolves `STILL_NEEDS_DONE_002.md` item #1 (Polymarket user/fill stream auth).

Staircase: **A → C → B → D** (data reads → execution writes → user stream → account sync). Each stair ships independently; each gets its own design + plan cycle.

Work orders (umbrella):
11. **STAIR_A_BATCH_ENDPOINTS_001** — batch `/midpoints`, `/prices`, `/spreads`, `/last-trade-price`, `/tick-size`; replace 180 parallel `/book` GETs with batched calls
12. **STAIR_C_LIVE_EXEC_BUILD_001** — `signer.py` protocol + `DummySigner` + `live_exec.py` with `place_order`/`cancel_order`/`cancel_all`; two independent kill-switch gates (`PHASE` + `LIVE_TRADING_KILL_SWITCH`)
13. **STAIR_B_USER_STREAM_001** — `ws/user` subscription; TRADE/ORDER event parser; sqlite integration; unblocks `RUNTIME_USER_STREAM_AUTH_UNBLOCK_001` from April 18
14. **STAIR_D_ACCOUNT_SYNC_001** — boot-time reconcile of `/positions`, `/trades`, balance vs. local sqlite; drift detection

Full design: `docs/superpowers/specs/2026-04-20-polymarket-integration-design.md`.

## Dependencies

```
1 → 2 → 3
1 → 8 → 9 → 10
4, 5, 6, 7  (independent, can run in parallel)
11 → 12 → 13 → 14   (P3 staircase; strict linear; each stair observed before next)
P0 complete → P3 can start (P3 leans on attribution fields)
```

P2 (replay) cannot start until P0 (attribution data) is in place — otherwise replay reproduces garbage.
P3 (Polymarket integration) leans on P1 paper slippage model (for paper-vs-live fill realism) but can start before P2.

## Success criteria

After P0 complete:
- Every closed paper trade in `trades_sports.db` has all attribution fields populated.
- Dashboard shows a calibration curve that updates live.
- Operator can answer "is the model calibrated?" in ≤ 10 seconds.

After P1 complete:
- No panel on the dashboard shows a number that isn't in the DB.
- Paper fills visibly differ from ideal mid (realistic slippage).
- No launcher process has a misleading name.

After P2 complete:
- Operator can sweep 5 gate/threshold configs against last 7 days of sessions in < 2 minutes.
- Sweep output includes calibration per config.

After P3 complete:
- Every batch-capable Polymarket endpoint (midpoints/prices/spreads/last-trade-price/tick-size) is wired through the typed `polymarket_client` facade.
- `live_exec.py` exists, is unit-tested against `DummySigner`, and is gated behind two independent env flags — neither flipped during this cycle.
- `ws/user` subscription populates sqlite `trades` fills in realtime (paper-mirror mode) and real fills in future live mode.
- `account_sync` runs on boot and logs a reconcile report (skip-log in paper mode, real diff in live mode).
- Setting `PHASE=live` + `LIVE_TRADING_KILL_SWITCH=false` + a real signer is the *only* change needed to place real orders. No additional code work required at call sites.

## Work-order execution

Each of the 10 work orders is dropped as a `HANDOFF_*.md` + `TASK_*.json` pair into `C:\Users\johnny\Desktop\BOT_BRIDGE\05_INBOX_FROM_MANAGER\`. Worker reads them, executes, writes `RESULT_*.json` to `06_OUTBOX_FROM_WORKER\`. Operator reviews results, approves, next task unblocks.

## Non-goals / explicit guards for workers

Every task will carry these `forbidden_actions`:
- No model/recommendation algorithm changes
- No new sports or event types
- No changes to bankroll/sizing logic (separate track)
- No changes to backfill/hydration scripts (separate track)
- No real-money execution code paths ← **exception for P3**: code paths are built but gated off by default; P3 tasks carry explicit gating-proof requirements instead of this ban

## Open questions (operator resolves during P1 verification, not blocking)

- **REGISTRY_PREGAME_WINDOW_001** — should registry window be fixed (2 days) or configurable? Leaving to worker proposal.
- **PAPER_SLIPPAGE_MODEL_001** — default slippage curve: start with a conservative fixed model, tune later once attribution shows real-vs-expected gap.
