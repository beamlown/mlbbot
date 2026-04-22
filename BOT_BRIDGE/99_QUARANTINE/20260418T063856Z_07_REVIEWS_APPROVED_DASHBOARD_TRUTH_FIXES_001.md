# APPROVED_DASHBOARD_TRUTH_FIXES_001

Status: APPROVED

I reviewed the implementation and approve it for manager handoff.

## Why approved
- Scope stayed tight to `sports_bot_v2/dashboard.html`, matching task rules.
- All three requested truth fixes were implemented without expanding scope:
  1. Positions-tab realized P&L now reads authoritative state value
  2. `mark_source` is now rendered on position cards as compact fallback chips
  3. R25 sublabel now reads `s.r25.sample_size` instead of a missing field
- Existing open positions, bankroll strip, win-rate display, and game feed behavior were preserved.

## Verification reviewed
- Review artifact confirms html-only code change
- Runtime API values align with new realized P&L source path
- SSE backend still exposes `mark_source`, and UI now surfaces it

## Implementation commit
- `73a4103`

## Worker artifacts
- `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_DASHBOARD_TRUTH_FIXES_001.json`
- `C:\Users\johnny\Desktop\BOT_BRIDGE\07_REVIEWS\REVIEW_DASHBOARD_TRUTH_FIXES_001.md`
