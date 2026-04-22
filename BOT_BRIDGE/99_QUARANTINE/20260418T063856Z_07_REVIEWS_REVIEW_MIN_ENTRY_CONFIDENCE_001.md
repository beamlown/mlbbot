# REVIEW — MIN_ENTRY_CONFIDENCE_001
**Date:** 2026-04-10
**Verdict:** APPROVED

## Scope check
- Files changed: `core/risk.py`, `.env` only — matches allowed_files exactly
- No forbidden files touched

## Acceptance criteria
| Criterion | Result |
|---|---|
| MIN_ENTRY_CONFIDENCE=0.60 in .env | PASS |
| risk.py reads MIN_ENTRY_CONFIDENCE with default 0.60 | PASS |
| Gate is FIRST check in check_entry_gates() waterfall | PASS — runs before spread, OB, depth, DB |
| Rejection reason matches existing format | PASS — confidence_too_low:X:0.600 |
| signal_confidence=None rejected | PASS |
| MIN_ENTRY_CONFIDENCE=0.0 disables gate | PASS |
| All existing gates untouched | PASS |
| py_compile passes | PASS |

## Coexistence note
risk.py already had MIN_CONFIDENCE=0.25 (env) with mode multipliers applied as eff_min_conf. The new MIN_ENTRY_CONFIDENCE=0.60 is an absolute hard floor that runs before the mode-aware system. Both gates are valid and non-conflicting: hard floor catches anything below 0.60, mode-aware system operates above that threshold.

## Restart required: YES
