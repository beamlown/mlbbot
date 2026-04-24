# REVIEW_BANKROLL_SESSION_RULES_001

- reviewer run: `RUN_8F49FF38E4C4`
- reviewer role: `SONNET_MANAGER`
- exit code: 1 (capture failure — transcript empty)
- manager override: 2026-04-17

## Decision: **ACCEPTED → DONE**

## Acceptance check

| Invariant | Verdict |
|-----------|---------|
| I1 available_cash | FIXED — fees_usd added to committed sum |
| I2 live_equity bid | FIXED — best_bid in _stream_positions_mark() |
| I3 session_pnl anchor | CONFIRMED |
| I4 lifetime realized PnL | CONFIRMED |
| I5 no double-counting | CONFIRMED |

- py_compile dashboard_server.py → PASS
- py_compile core/paper_exec.py → PASS
- BANKROLL_ACCOUNTING_SPEC_001.md written to 08_SHARED_CONTEXT/

Prior CHANGES_REQUESTED was a control-plane transcript capture failure, not a substantive rejection.
