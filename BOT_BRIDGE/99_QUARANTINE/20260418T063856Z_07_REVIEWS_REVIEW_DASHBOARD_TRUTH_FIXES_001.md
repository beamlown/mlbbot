# REVIEW — DASHBOARD_TRUTH_FIXES_001
**Date:** 2026-04-10
**Verdict:** APPROVED

## Scope check
- Edited file: `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html` only (code changes)
- No scope expansion beyond requested 3 fixes

## Fix verification
1. **Positions tab Realized P&L**
   - PASS: replaced closed-slice sum with authoritative `state.pnl.realized` (fallback `state.bankroll.net_pnl`).
2. **mark_source on position cards**
   - PASS: cards now render compact fallback chips (`mark REST` / `mark POLL`) while keeping existing trade-source chips unchanged.
3. **R25 sublabel 0 trades issue**
   - PASS: switched from `s.total_closed` to `s.r25?.sample_size`.

## Regression check
- Open positions panel behavior: unaffected
- Bankroll strip behavior: unaffected
- R25 win-rate percentage behavior: unaffected
- Game feed behavior: unaffected

## Notes
- SSE backend still exposes `mark_source` (confirmed in `dashboard_server.py`).
- Runtime API values (`/api/state`, `/api/bankroll`) align with new authoritative realized-source path.
