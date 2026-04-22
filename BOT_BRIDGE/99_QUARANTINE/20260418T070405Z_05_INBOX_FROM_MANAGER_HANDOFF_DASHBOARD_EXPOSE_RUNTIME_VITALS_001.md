# HANDOFF_DASHBOARD_EXPOSE_RUNTIME_VITALS_001

## Status: ACTIVE

**Title**: Dashboard: expose rolling perf, guard blocks, mode state, bankroll detail, recent trades
**Priority**: HIGH
**Subsystem**: sports_bot_v2 / dashboard
**Issued**: 2026-04-17
**Assigned**: SONNET_MANAGER

---

## What this task is

_(edit me — auto-generated stub)_

## Allowed files
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html`
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_v2.html`
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`

## Forbidden files
- `C:\Users\johnny\Desktop\sports_bot_v2\bot_core.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\core\paper_exec.py`

## Acceptance

On http://localhost:8900 the operator can see (without opening DevTools): (1) rolling r25/r50/r100 win_rate + expectancy + pnl, (2) guard_block_rate + the current guard_reasons list, (3) mode block (name, score, switch_reason, multipliers, dwell), (4) bankroll detail (start, current, pct_gain, capital_committed, available_cash, session_pnl), (5) recent_closed trades table with slug, side, reason_close, pnl_usd, entry_px, exit_px, (6) exit_reason_counts distribution, (7) market_cooldowns_active and invalid_market_blocks counters, (8) total_trades lifetime. All fields already exist in /api/state — this is pure render work; no new endpoints required.

---

_Auto-generated stub. Replace with narrative brief; the dashboard will not overwrite this file once it exists._
