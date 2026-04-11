# REVIEW — DASHBOARD_MARK_SOURCE_AND_GUARD_MESSAGE_AUDIT_001
**Reviewer:** Claude (manager)
**Date:** 2026-04-10
**Verdict:** PARTIAL PASS — surface-layer questions answered; upstream payload origin not fully traced

---

## What was answered

| Question | Status |
|----------|--------|
| Why do cards show `mark REST`? | ANSWERED — `dashboard_server.py` sets `mark_source='rest_fallback'` when stale REST polling refreshes a mark; `dashboard.html` renders it as a chip. Expected behavior, not a dashboard bug. |
| Is `mark REST` chip a binding error? | ANSWERED — No. Chip is intentional, correctly bound to `mark_source` value in position payload. |
| Where does guard/warning text originate? | PARTIALLY ANSWERED — dashboard.html renders raw `state.last_guard_result` or `state.guard` key/value badges; no hardcoded "max down" label in dashboard code. Upstream source not confirmed. |
| Is there an active max-down runtime condition? | PARTIALLY ANSWERED — `state.json` showed null for all guard fields at time of audit. Cannot confirm or rule out transient upstream source. |

---

## Residual gaps (drive MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001)

**Gap 1 — Fallback frequency unassessed.**
The audit confirmed `rest_fallback` is the mechanism but did not determine whether fallback is occurring occasionally as designed or too often (degraded stream). The payload trace task must answer this.

**Gap 2 — Guard payload origin not traced to source.**
`state.last_guard_result` and `state.guard` were null at audit time. The wording source for any prior "max down" style message was not located. Whether it originates in bot_core loop logic, server-side payload assembly, or a stale cached state write is unknown.

**Gap 3 — `mark_source` production chain not traced to source function.**
The audit noted `dashboard_server.py` produces the value from "state hub marks" but did not identify the specific function, field, or decision logic that switches between `stream`, `rest_fallback`, and `poll_fallback`.

---

## Acceptance criteria check

| Criterion | Status |
|-----------|--------|
| read_only_confirmed | PASS |
| mark_source chain documented from state.json to chip | PARTIAL — state.json → /api/stream/state → dashboard.html confirmed; origin in dashboard_server.py identified but not traced to the specific decision branch |
| Cause label (a/b/c/d/e) for mark REST | PASS — cause (a): normal short-term stale-mark fallback behavior |
| "max down" trigger identified | PARTIAL — not hardcoded in dashboard; upstream origin unconfirmed |
| Actual guard_reasons from live state | PASS — guard fields null at time of audit |
| Message accuracy assessment | PARTIAL — cannot confirm or deny without live guard payload |
| Root-cause classification | PARTIAL — dashboard layer cleared; upstream not confirmed |

---

## Decision

**PARTIAL PASS.** Dashboard HTML and dashboard_server.py are cleared as root-cause sources of both symptoms. The `mark REST` chip is expected behavior. The "max down" wording source and fallback frequency are unresolved. Follow-on task MARK_FALLBACK_AND_GUARD_PAYLOAD_TRACE_001 opened to complete the trace.
