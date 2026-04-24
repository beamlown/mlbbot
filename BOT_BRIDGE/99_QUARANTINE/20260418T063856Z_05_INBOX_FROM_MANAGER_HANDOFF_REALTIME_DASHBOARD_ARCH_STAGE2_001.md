# HANDOFF - REALTIME_DASHBOARD_ARCH_STAGE2_001
## Add minimal SSE live metric slice with polling fallback intact

Allowed files:
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html`
- BOT_BRIDGE task/result/review files

No new files were needed for Stage 2.

SSE route:
- `GET /api/stream/state`

Stage 2 payload fields:
```json
{
  "type": "positions_mark",
  "ts": "...",
  "source": "dashboard_server",
  "stale": false,
  "open_count": 3,
  "live_equity_total": 148.22,
  "positions": [
    {
      "market_slug": "mlb-...",
      "current_price": 0.61,
      "current_price_stale": false,
      "unrealized_pnl_usd": 4.08,
      "live_equity_usd": 54.92
    }
  ]
}
```

Stage 2 push-driven path:
- held-side current price
- unrealized PnL
- live equity
- aggregate live equity total
- stream freshness/staleness text

What stays on polling fallback untouched:
- `/api/state`
- `/api/trades`
- shadow polling
- games polling
- bankroll polling

Rollback:
- remove `/api/stream/state` and `ensureStateStream()/applyStreamPositionsMark()` hookup
- polling continues to function as before
