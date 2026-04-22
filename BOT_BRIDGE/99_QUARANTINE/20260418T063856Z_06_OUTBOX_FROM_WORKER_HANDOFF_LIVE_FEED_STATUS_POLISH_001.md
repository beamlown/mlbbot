# LIVE_FEED_STATUS_POLISH_001 Handoff

## Files changed
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html`

## Frontend-only
Yes. No backend change was needed.

## Exact labels/copy changed
- `stream stale ${timeAgo(latestStreamTs)}` → `Market feed stale · ${humanAge(latestStreamTs)}`
- `stream live ${timeAgo(latestStreamTs)}` → `Market feed live`
- missing stream timestamp state → `Market feed reconnecting`
- `Market price unavailable, live P&L and live equity may be incomplete` → `Market pricing is currently unavailable, so live value may be incomplete`
- `Market price is stale, live P&L and live equity may lag` → `Market pricing is stale, so live value may lag`
- `Best bid` missing `—` → `No bid`
- `Best ask` missing `—` → `No ask`
- `Spread` missing `—` → `Unavailable`
- `Game freshness` unknown `—` → `Status available, freshness unknown` or `Freshness unknown`
- `Market freshness` unknown `—` → `Feed age unavailable`

## Before/after wording examples
- before: `stream stale -123s`
- after: `Market feed stale · 2m 3s ago`

- before: `stream live 4s`
- after: `Market feed live`

- before: `Best bid —`
- after: `Best bid No bid`

- before: `Game freshness —`
- after: `Game freshness Status available, freshness unknown`

## Scope control
Only dashboard presentation copy/formatting was changed. No strategy, execution, or backend behavior was touched.
