# REVIEW — CONFIDENCE_HISTORY_AUDIT_001
**Reviewed by:** Claude (manager)
**Date:** 2026-04-10
**Verdict:** APPROVED

---

## Summary

Read-only audit of 178 executed trades and 41,248 shadow recommendation records across a 6–7 day window. Complete data — confidence field populated for 100% of records in both sources.

---

## Acceptance Criteria Check

| Criterion | Result |
|-----------|--------|
| Sample window documented | PASS — 6 days of trades, 7 days of shadow recs |
| Distribution in required bins | PASS — all 6 bins reported for both executed trades and shadow recs |
| Floor impact quantified | PASS — % pass/fail at 0.60 for both sources |
| Trade list (25 records) | PASS — last 25 trades with confidence, status, and floor flag |
| Recommendation view | PASS — 41,248 shadow recs summarized |
| Conclusion with recommendation | PASS — keep 0.60, reasoning documented |
| Where confidence is stored | PASS — DB column, log lines, shadow rec JSON all documented |
| read_only_confirmed | PASS |
| No DB writes | PASS |

---

## Key Findings (for operator)

- **69% of historically executed trades would be blocked** by the 0.60 floor
- **86% of raw model signals** would be suppressed
- Distribution is **bimodal**: most signals cluster at 0.33–0.40 or 0.62–0.65; the 0.50–0.60 zone is nearly empty
- Practical consequence: lowering the floor to 0.55 or 0.58 only recovers ~4–8 percentage points of trade frequency — not a meaningful difference
- Two currently live open trades (223, 224) were entered below the floor under the old system; they will run to their existing exit conditions

---

## Operator Note

The bimodal structure is significant. The 0.60 floor is a sharp quality gate that effectively selects only the high-conviction cluster. If trade frequency is judged too low in practice, the right lever is **broader market coverage** (more game lines, additional sports), not a lower confidence floor. Lowering to 0.55 or 0.58 recovers almost nothing.

---

## Decision

**APPROVED** — clean read-only audit. Findings are clear and actionable. No changes requested.
