# REVIEW_SESSION_MARKET_TRADE_CAP_001.md

## Verdict
APPROVED

## Decision
Approve `SESSION_MARKET_TRADE_CAP_001`. Move to DONE. `POST_GAP_STOP_SAME_SIDE_SESSION_BAN_001` is next in the serial chain (bot_core.py). `RESTART_CONFIG_HASH_VERIFY_001` activates when cold restart is confirmed.

## What was confirmed

- Only `bot_core.py` and `.env` modified — `core/risk.py` not touched.
- Pre-gate check inserted in bridge loop after LATE_INNING_BLOCK check, before `check_entry_gates()` — consistent pattern.
- `MAX_SLUG_ENTRIES_SESSION` module-level constant added (line 108), reads from env with default 3.
- DB query: `SELECT COUNT(*) FROM trades WHERE market_slug = ? AND date(ts_open) >= date('now', 'localtime')` — includes both open and closed trades, today only.
- Uses existing `DB_PATH` module-level constant — no redundant env read.
- Rejection log format: `BRIDGE GATE REJECT [check_entry_gates] slug=... reasons=['session_slug_cap_exceeded:N>=3']` — matches required format.
- Exception handler wraps the DB query — silently skips on failure (safe default, does not break gate waterfall).
- `MAX_SLUG_ENTRIES_SESSION=3` added to `.env`.
- `python -m py_compile bot_core.py` — PASS.
- Restart required — correctly noted.

## One runtime observation

The query uses `date('now', 'localtime')` for today's date boundary. If a session runs across midnight, trades from the previous calendar day will not count toward the new day's cap. This is the correct behavior for a per-session cap. No issue.

## Why this matters

Tonight's worst losses (CWS-KC: 9 entries, -$145; HOU-SEA: 9 entries; COL-SD: 8 entries) all came from unlimited re-entry on the same market. After this fix, the bot is capped at 3 entries per slug per day regardless of how many times MAX_TRADES_PER_MARKET resets on position close.

## File locks released

- `bot_core.py` — RELEASED
- `core/risk.py` — was never locked

## Next tasks

- `POST_GAP_STOP_SAME_SIDE_SESSION_BAN_001` — next in serial chain, locks bot_core.py
- `RESTART_CONFIG_HASH_VERIFY_001` — activate when cold restart confirmed by operator

## Manager judgment

Close `SESSION_MARKET_TRADE_CAP_001` to DONE.
Dispatch `POST_GAP_STOP_SAME_SIDE_SESSION_BAN_001`.
