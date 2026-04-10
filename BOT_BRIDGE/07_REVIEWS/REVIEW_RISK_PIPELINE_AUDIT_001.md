# REVIEW_RISK_PIPELINE_AUDIT_001

**Decision: APPROVED**
**Reviewed: 2026-04-10**

---

## Scope check

- Task was read-only — no production file modifications. `git diff --name-only` confirmed empty. ✓
- All six audit surfaces were covered with `file:line` citations. ✓
- Report written to `08_SHARED_CONTEXT/RISK_PIPELINE_AUDIT_REPORT_001.md`. ✓
- All env threshold values cited with exact `.env` line numbers. ✓
- Preflight checks (py_compile, imports) all passed. ✓

---

## What the audit found

The audit task itself is complete and correct. The findings are real and well-evidenced. Worker decision of CHANGES_REQUESTED is understood as "follow-up remediation needed" rather than audit task failure — the audit task itself is approved as complete.

**1 broken invariant confirmed (HIGH):**
- `market_resolved` force-close path (`bot_core.py:570-577`) calls `close_trade()` with a dict missing `reason_close` and `ts_close`. `core/db.py:131-139` uses `.get()` so both write NULL. Log line still fires. DB audit trail is incomplete.

**5 gaps confirmed:**

| gap | severity | covered by |
|-----|----------|------------|
| market_resolved close omits reason_close/ts_close | HIGH | → MARKET_RESOLVED_DB_FIELDS_001 (new task) |
| No per-session max loss cap | HIGH | → SESSION_LOSS_CAP_001 (new task) |
| No daily max loss cap | HIGH | → SESSION_LOSS_CAP_001 (new task) |
| Sizing not bankroll/drawdown-aware | HIGH | → POSITION_SIZING_RULES_001 (already queued, already in scope) |
| /api/bankroll uses 30-day sum not canonical lifetime PnL | MED | → BANKROLL_SESSION_RULES_001 (already queued, already in scope) |

---

## Acceptance criteria met

- Report covers all 6 required surfaces ✓
- Every gap listed with file:line reference ✓
- Broken invariants table complete ✓
- Immediate risks ranked ✓
- No production file modified ✓

---

## Follow-up actions triggered

Two new tasks written to 05_INBOX_FROM_MANAGER:
- `TASK_MARKET_RESOLVED_DB_FIELDS_001.json` — HIGH, bot_core.py, ACTIVE
- `TASK_SESSION_LOSS_CAP_001.json` — HIGH, bot_core.py + core/risk.py, QUEUED (file conflict with above)

Board: TP_SL_SCHEMA_NORMALIZATION_001 promoted to ACTIVE (its gate dependency is now APPROVED).
