# HANDOFF — SESSION_PNL_TRUE_START_FIX_001
**Priority:** MEDIUM
**Type:** Code fix — session accounting
**Issued:** 2026-04-11
**Status:** QUEUED — lower priority; execute after risk-fix tasks are DONE
**Scope:** NARROW — session_start_ts in bot_core.py or dashboard_server.py only. Do not touch PnL math, exit logic, or trade execution.

---

## One-sentence task

Fix session PnL tracking so it reflects the actual trading session start (e.g., start of the current calendar day or first trade of the day), not just the last process restart timestamp.

---

## Why this exists

Tonight's audit found that `state.json` `session_start_ts` = 1775868622 = 2026-04-11T00:50:22 UTC — the most recent restart. But trading actually began at 18:23 UTC on 2026-04-10 (approximately 6.5 hours earlier). The session PnL field on the dashboard therefore only counts losses after 00:50:22 and misses the majority of the evening's drawdown.

**The problem compounds during multi-restart sessions:** every restart resets the session PnL baseline, making the session number meaningless as a session risk indicator.

---

## What you must NOT do

- Touch `check_entry_gates()`, exit logic, or trade math
- Refactor the full PnL accounting system
- Touch dashboard.html rendering if the fix lives in bot_core.py / dashboard_server.py only
- Change realized PnL calculation (that is already correct)

---

## Preferred approach

**Option A — Calendar-day session start (preferred)**

On startup, set `session_start_ts` to the start of the current UTC calendar day (00:00:00 UTC), not `time.time()`.

```python
from datetime import datetime, timezone, timedelta
_today_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
session_start_ts = _today_utc.timestamp()
```

When computing `session_pnl` in `dashboard_server.py`, filter trades by `ts_open >= session_start_ts` (already done; just the value changes).

**Option B — Persist and reload session_start_ts**

Write `session_start_ts` to `state.json` on each write. On restart, reload it if the saved value is from the same UTC calendar day; otherwise set it to today's start.

If Option A is simpler and the worker judges it sufficient, use it. Justify in result.

---

## Acceptance criteria

- [ ] Session PnL covers all trades from the current UTC calendar day (or since first-trade-of-day if Option B), not just since last restart
- [ ] Multiple restarts within the same day do not reset the session_start_ts to a later time
- [ ] `python -m py_compile` passes for any modified file
- [ ] No other behavior changed

---

## Required output

Write result to:
```
C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_SESSION_PNL_TRUE_START_FIX_001.json
```
