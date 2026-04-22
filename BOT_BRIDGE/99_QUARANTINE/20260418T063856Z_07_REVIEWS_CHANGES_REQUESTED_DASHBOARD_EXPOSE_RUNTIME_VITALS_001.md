# CHANGES_REQUESTED_DASHBOARD_EXPOSE_RUNTIME_VITALS_001

Status: CHANGES_REQUESTED
Reviewer: Opus · Patch Reviewer
Reviewed: 2026-04-17

## Summary

The 8 System-tab sections mostly landed and look good, but the Mode section
is missing two fields explicitly required by the acceptance criteria, and
the worker made several unrelated changes outside the "System tab render
only" mandate. Fix the two acceptance gaps and this can be approved.

## Blocking: acceptance criteria #3 incomplete

Acceptance criteria #3 requires the mode block to show **name, score,
switch_reason, multipliers, dwell**. `renderSystemTab()` in
`dashboard.html` (around line 1578–1588) renders only name, score,
dwell_trades. Missing:

1. **`mode.switch_reason` — not rendered at all.** The handoff asks for
   it as a one-liner. Add a row or dedicated cash-box rendering it
   (fall back to '—' when empty).
2. **`mode.multipliers` — extracted into `mults` but never rendered.**
   `const mults = mode.multipliers || {};` is dead code. The handoff
   requires a tight key/value grid for min_confidence, max_spread,
   min_depth_usd, max_concurrent.

Both fields are already populated in `/api/state`; this is a pure HTML
render addition in the same renderSystemTab function.

## Non-blocking: scope creep to document or split off

These changes are in this worker's diff but were NOT requested by the
handoff. They aren't harmful on their own but should be called out:

- **`/api/bankroll` lifetime sum fix** (dashboard_server.py ~line 949) —
  switched from 30-day history sum to a full SUM query. This is a
  legitimate bug fix for the bankroll endpoint but is unrelated to the
  dashboard System tab render task. Recommend splitting into its own
  task or documenting it explicitly in the RESULT.
- **Live-game monitor redesign** (`renderLiveGamesFocus`,
  `buildUnifiedPositionCards`, count-chip CSS, score-block CSS) — this
  is substantive UI restructuring of the Live tab, not the System tab
  the handoff scoped. Operator may like it, but it was not asked for
  and introduces review surface outside the stated scope.
- **Games-tab date-suffix slug stripping** in `renderGamesTab` — bug
  fix for key matching that is off-scope here.
- **`current_batter` / `current_pitcher` fields added to
  `_build_games_from_raw`** — widens the game-state payload shape. The
  handoff explicitly said *"No new state fields. If a desired view
  needs a field not in /api/state, file a separate task; do not widen
  the scope here."* This belongs to the live-monitor redesign above;
  same remediation (split or document).

## Not attributed to this worker

The following working-tree changes overlap with this diff but are the
approved BANKROLL_SESSION_RULES_001 work that has not been committed
yet. Reviewer verified against `APPROVED_BANKROLL_SESSION_RULES_001.md`:

- `fees_usd` included in `_compute_open_trade_accounting`
  `capital_committed`.
- `best_bid`-based `live_equity_usd` / `unrealized_pnl_usd` in
  `_stream_positions_mark`.
- `available_cash` removed from `_compute_open_trade_accounting`
  return (only `_read_state` uses it; verified no other callers).

Not counted against this review.

## What landed correctly

- Runtime freshness chip with <30s / 30–120s / stale thresholds.
- Rolling Performance cards: r25/r50/r100 with sample size, W/L,
  win-rate, expectancy. Expectancy colour-coded green/red.
- Guard Block Status: big % (red if >50%), reason chips.
- Bankroll Status: start, current, pct_gain colour-coded, committed,
  available, session P/L colour-coded, open trade count. session_start
  not rendered as human time but `session_start` variable is unused —
  acceptable miss, not blocking.
- Recent Closed Trades (last 10): slug, side, reason_close chip
  (colour-coded take_profit/stop_loss/manual_stale_close/manual_close),
  signed pnl_usd, entry_px→exit_px.
- Exit Reasons distribution + market_cooldowns_active +
  invalid_market_blocks counters.
- Lifetime counters: total_trades, loop_count, config_hash first 8,
  bridge on/off.
- `r50`/`r100` rolling windows computed server-side in
  `dashboard_server.py` `_read_state` using the trades DB, same pattern
  as the existing r25 logic. Defensible even though it widens
  `/api/state` shape slightly — handoff was self-contradictory on this
  point (claimed fields existed; they did not). Adding them at the
  dashboard layer rather than in `bot_core.py` respects the forbidden
  files list.

## Re-review checklist

1. `mode.switch_reason` rendered (with `—` fallback).
2. `mode.multipliers` rendered as key/value grid (min_confidence,
   max_spread, min_depth_usd, max_concurrent).
3. Either split the live-monitor + /api/bankroll + games-tab changes
   into separate tasks OR update the RESULT summary to explicitly list
   them as additional fixes, so they aren't invisible.

No other changes required. The rest of the System tab is good work.
