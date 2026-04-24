# HANDOFF_DASHBOARD_EXPOSE_RUNTIME_VITALS_001

## Status: READY_FOR_WORKER

**Title**: Dashboard — expose runtime vitals the operator currently can't see
**Priority**: HIGH (operator flying blind on a 100% guard-block rate right now)
**Subsystem**: sports_bot_v2 / dashboard
**Issued**: 2026-04-17
**Filed by**: control_plane observation loop

---

## Why this task exists

During a live monitoring session, the control plane compared what
`GET http://localhost:8900/api/state` returns against what the HTML
dashboard actually renders. Large amounts of critical runtime state
exist in the JSON payload but never make it to the operator's eyes.

The most visible symptom: the bot is currently blocking 100% of trade
signals (`guard_block_rate: 1.0` with reasons `micro_depth_too_low`,
`micro_spread_too_wide`, `late_inning_block`). Bridge-gate PASS lines
are showing up in `logs/bot_core_launcher.log` for several mlb-*-2026-04-17
slugs, but every one is then killed downstream by a guard — and the
dashboard shows no hint of this. The operator has to tail log files to
know anything is happening.

## Sections to add to the dashboard

Each of these is ALREADY present in `/api/state`. This is pure render
work — no new endpoints, no new state collection.

1. **Rolling performance**
   - Three horizontal cards or a compact table: r25, r50, r100
   - Per window: `n`, `wins`/`losses`/`breakeven`, `win_rate` (%), `pnl`,
     `avg_win`, `avg_loss`, `expectancy`
   - Colour expectancy green if > 0, red if < 0

2. **Guard block visibility**
   - `guard_block_rate` as a large percentage (currently 100% — that
     should be screaming at the operator in red)
   - The current `guard_reasons` list rendered as chips

3. **Mode block**
   - `mode.mode` (neutral / aggressive / conservative)
   - `mode.score` and `mode.dwell_trades` (e.g. `dwell=0/5`)
   - `mode.switch_reason` as a one-liner
   - `mode.multipliers` as a tight key/value grid
     (min_confidence, max_spread, min_depth_usd, max_concurrent)

4. **Bankroll detail card**
   - `bankroll.start`, `bankroll.current` (large), `bankroll.pct_gain`
     (green/red), `bankroll.capital_committed`, `bankroll.available_cash`,
     `bankroll.session_pnl`, `bankroll.open_trade_count`
   - Show `session_start_ts` as a readable local time

5. **Recent closed trades**
   - Table of `recent_closed` (last 10): id, market_slug, side,
     reason_close (chip — colour-code: take_profit=green,
     stop_loss=red, manual_stale_close=gray), pnl_usd (signed),
     entry_px → exit_px
   - Sort newest first (it already is in the payload)

6. **Exit reason distribution**
   - `exit_reason_counts` as a small bar or pill chart
   - Helps the operator see if the bot is hitting stops disproportionately

7. **Market friction counters**
   - `market_cooldowns_active`
   - `invalid_market_blocks`
   - `market_validity_blocks` breakdown if non-empty
   - `last_invalid_market_details` in a collapsed detail row

8. **Lifetime counters**
   - `total_trades` somewhere in the header or footer
   - `loop_count` (already exists? double-check)
   - `config_hash` short form (first 8 chars) as a chip so the operator
     can see at a glance if a config reload changed it

## Freshness indicator

- `file_age_sec` and the `stale` boolean should drive a subtle header
  chip: green if fresh (<30s), amber 30–120s, red if `stale` is true.

## Where to edit

The dashboard server is a raw `http.server` in
`C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`. The
operator-facing HTML lives in either `dashboard.html` or
`dashboard_v2.html` — check which one `GET /` serves and edit that.
You may also edit both if they're branches of the same UI; pick the
one being served as canonical and document in the RESULT which file
is live.

The `/api/state` JSON is already populated; do not change its shape.

## Out of scope (do NOT touch)

- `bot_core.py`, `core/paper_exec.py`, any file in `core/` — this task
  is render-only.
- No new state fields. If a desired view needs a field not in
  `/api/state`, file a separate task; do not widen the scope here.

## Result expectations

- `RESULT_DASHBOARD_EXPOSE_RUNTIME_VITALS_001.json` with
  `status: ok`, `summary: "<one-liner on what landed>"`, and
  `files_changed` listing the exact files touched (absolute paths).
- If the active template turns out to be a third file neither you nor
  this handoff foresaw, treat that as blocked and describe what you
  found — do not pick arbitrarily.

---
## RETRY CONTEXT (auto-generated — attempt 3)

A previous run failed on this task. Before you start, read this:

- prior status: `fail`
- prior summary: (no RESULT_JSON emitted and no RESULT file written)
- prior run id: `RUN_A56F200915F0`

### What went wrong
The previous worker did not produce a RESULT for **DASHBOARD_EXPOSE_RUNTIME_VITALS_001**. Common causes: (a) the worker drifted to a different task, (b) the worker never wrote `RESULT_DASHBOARD_EXPOSE_RUNTIME_VITALS_001.json`, (c) the worker exited before completing the scope.

### What to do differently this attempt
1. Work ONLY on `DASHBOARD_EXPOSE_RUNTIME_VITALS_001`. Ignore every other task name you see.
2. Write your result to `BOT_BRIDGE/06_OUTBOX_FROM_WORKER/RESULT_DASHBOARD_EXPOSE_RUNTIME_VITALS_001.json` and NO other file.
3. If the scope is unclear, emit `status: blocked` with a specific question.
   Do NOT substitute a different task you think you know.

### Prior stdout tail (for diagnosis)
```
  - Exit reason distribution
  - Market friction counters
  - Lifetime counters + freshness indicator

### What I did:
Updated **dashboard_server.py** `_read_state()` function to ensure all required fields (guard_block_rate, guard_reasons, mode, exit_reason_counts, market_cooldowns_active, invalid_market_blocks, total_trades, loop_count, config_hash) have safe defaults if missing from the bot's state.json. This prevents dashboard breakage while the bot updates its output format.

**File changed:** `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`

The dashboard is now ready to display all vitals once the bot's runtime state.json populates these fields.
[done] ok duration=75289ms turns=14
[usage] input=7980 output=7373 cache_read=804204 cost_usd=0.1926
```
