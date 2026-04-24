# HANDOFF: SESSION_MARKET_TRADE_CAP_001

## What you are doing
Adding a per-session trade count cap per market slug to `bot_core.py`. After 3 total entries on the same market in one session, block further entries on that slug for the rest of the session.

## Why this exists
Tonight the bot placed 9 sequential trades on mlb-cws-kc (all losing) and 9 on mlb-hou-sea. Existing gate `MAX_TRADES_PER_MARKET=1` only blocks *concurrent* positions — it resets when the prior position closes. There is no cap on cumulative re-entries. The bot followed CWS-KC from 0.62 down to 0.05, opening a new BUY_YES every time the prior one stopped out.

## The fix — exactly what to implement
Inside the entry gate path (in `bot_core.py`, before or as part of `check_entry_gates()`):
- Query the DB: `SELECT COUNT(*) FROM trades WHERE market_slug = ? AND date(ts_open) >= date('now', 'localtime')`
- If count >= `MAX_SLUG_ENTRIES_SESSION` (default 3), reject with reason `session_slug_cap_exceeded:{count}>={cap}`
- Log it: `BRIDGE GATE REJECT [check_entry_gates] slug=... reasons=['session_slug_cap_exceeded:3>=3']`

Add `MAX_SLUG_ENTRIES_SESSION=3` to `.env`.

## Constraints
- Only touch `bot_core.py`, `core/risk.py`, and `.env`
- Do not touch dashboard, stream, or exit logic
- Do not change the existing `MAX_TRADES_PER_MARKET` behavior — this is additive
- The count must include both open and closed trades for today

## What you must verify
- py_compile passes on every changed file
- The rejection reason string matches the standard gate format
- State explicitly whether a restart is required
