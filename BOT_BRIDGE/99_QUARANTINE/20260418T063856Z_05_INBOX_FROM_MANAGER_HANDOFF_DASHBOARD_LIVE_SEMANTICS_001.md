# HANDOFF - DASHBOARD_LIVE_SEMANTICS_001
## Clarify live card semantics for side, lifecycle, price, and equity

Allowed files:
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html`
- `dashboard_server.py` only if a tiny backend addition is truly necessary
- BOT_BRIDGE task/result/review files

Current semantic problem:
- `WIN / LOSE` was being used as a held-side label, but users could easily misread it as current result state or resolved outcome.
- pricing/equity math was mostly correct, but labels were too ambiguous.
- stale/unavailable market state was not prominent or honest enough.

Current formulas verified as correct:
- current price: `r.current_price ?? (r.resolved ? r.exit_px : null)`
- unrealized P&L:
  - YES: `(current_price - entry_px) * qty`
  - NO: `(entry_px - current_price) * qty`
- live equity: `qty * currentPx`
- available cash/backend committed math already correct in backend

Frontend-only fix chosen:
- replace ambiguous WIN/LOSE held-side wording with explicit side text like `TEAM TO WIN` / `TEAM TO LOSE`
- relabel `Current` to held-side price semantics
- make stale/unavailable market state explicit and honest
- relabel cash strip for immediate comprehension
- leave backend formulas unchanged

Rollback:
- Revert `dashboard.html` only
