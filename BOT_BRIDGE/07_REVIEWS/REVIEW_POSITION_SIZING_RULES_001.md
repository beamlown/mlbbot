# REVIEW_POSITION_SIZING_RULES_001

**Decision: APPROVED**
**Reviewed: 2026-04-10**

---

## Scope check

- Allowed files: `core/paper_exec.py`, `core/risk.py`. No production files modified. ✓
- `git diff` confirmed empty — documentation and audit only. ✓
- `SIZING_RULES_SPEC_001.md` written to `08_SHARED_CONTEXT/`. ✓
- `RESULT_POSITION_SIZING_RULES_001.json` written to `06_OUTBOX_FROM_WORKER/`. ✓

---

## Invariant evaluation

| Rule | Verdict | Evidence |
|------|---------|----------|
| SIZE_BOUNDED_PER_TRADE | ✓ CONFIRMED | `paper_exec.py:40` — `min(sized, MAX_POSITION_SIZE_USD)` = $100 cap on both tier path and recommended_size path (:76) |
| SIZE_BOUNDED_PER_SESSION | ✗ GAP (HIGH) | Count cap only (MAX_CONCURRENT_TRADES=3). No USD dollar cap. Deferred to BANKROLL_SESSION_RULES_001 with HIGH severity tag. |
| SIZE_PROPORTIONAL_TO_CONFIDENCE | ✓ CONFIRMED | Tier table: <0.70→1.0×, ≥0.70→1.25×, ≥0.80→1.50×. Explicit, env-configurable, code at `paper_exec.py:27-40`. |
| SIZE_RESPECTS_LIQUIDITY | ✓ CONFIRMED | Depth gate at `risk.py:188-190` blocks entry if depth < MIN_TOUCH_DEPTH_USD=200. Safety property: min_depth ($200) > max_size ($100), so size can never exceed available depth. |
| SIZE_EXPLAINABLE | ⚠ PARTIAL | Formula documented verbatim. Bankroll-agnostic by design currently — documented as HIGH gap. |
| QTY_CONSISTENT_WITH_COMMITTED_USD | ✓ CONFIRMED | `paper_exec.py:81` — `qty = size_usd / fill_px` ∴ qty × fill_px = size_usd exactly. `get_committed_usd()` in risk.py matches. |

---

## Acceptance criteria

- [x] All 6 sizing invariants evaluated — 4 confirmed, 1 gap documented with HIGH severity, 1 partial with gap documented
- [x] `SIZING_RULES_SPEC_001.md` written and complete with formula, tier table, caps, liquidity gate, worked example
- [x] Sizing formula documented verbatim with variable names matching code
- [x] `python -m py_compile core/paper_exec.py` — passes (no changes)
- [x] `python -m py_compile core/risk.py` — passes (no changes)
- [x] Only allowed_files in scope (none modified)
- [x] No threshold values changed

---

## Gaps forwarded to BANKROLL_SESSION_RULES_001

1. **SIZE_BOUNDED_PER_SESSION (HIGH):** Add `MAX_TOTAL_COMMITTED_USD` env cap; enforce sum of committed_usd across open trades before allowing new entry.
2. **Bankroll-aware sizing (HIGH):** Scale `PAPER_POSITION_SIZE_USD` relative to current bankroll or drawdown state.

---

## Rollback

No production code was modified. Rollback is trivially possible (nothing to undo).
