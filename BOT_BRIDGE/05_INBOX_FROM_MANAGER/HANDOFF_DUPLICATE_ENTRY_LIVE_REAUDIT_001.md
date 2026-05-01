# HANDOFF - DUPLICATE_ENTRY_LIVE_REAUDIT_001
## Live duplicate-entry protection re-audit

This is verification-only unless a hard failure is proven.

Read-only surfaces to inspect:
- `C:\Users\johnny\Desktop\sports_bot_v2\core\db.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\bot_core.py`
- live DB path resolved from current runtime/config
- live runtime state
- recent logs showing opens, duplicate skips, and capacity behavior

Required proof points:
1. Exact live DB path in use
2. Whether unique index `idx_trades_one_open_per_slug` exists in the live DB
3. Whether duplicate open rows currently exist for any `market_slug`
4. Whether the running stack still uses `insert_open_trade()` rather than bypassing it
5. Whether recent logs show fresh duplicate-open evidence or instead show guarded/capacity-limited behavior
6. Whether capacity is staying within configured limits

If a hard remaining failure is proven, stop and mark BLOCKED with exact files needed. Otherwise produce evidence-backed verification only.
