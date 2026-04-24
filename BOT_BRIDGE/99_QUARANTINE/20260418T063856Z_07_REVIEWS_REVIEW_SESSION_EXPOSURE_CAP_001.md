# REVIEW — SESSION_EXPOSURE_CAP_001
**Date:** 2026-04-10
**Verdict:** APPROVED

## Scope check
- Files changed: `core/risk.py`, `.env` only — matches allowed_files exactly
- No forbidden files touched

## Acceptance criteria
| Criterion | Result |
|---|---|
| MAX_TOTAL_COMMITTED_USD=150 in .env | PASS |
| risk.py reads MAX_TOTAL_COMMITTED_USD with default 150 | PASS |
| Gate blocks when committed + MAX_POSITION_SIZE_USD > cap | PASS |
| Rejection reason matches existing format | PASS — exposure_cap_exceeded:committed=X+Y>Z |
| MAX_TOTAL_COMMITTED_USD=0 disables gate | PASS |
| DB failure logs WARNING and skips gate (does not block entry) | PASS |
| All existing gates untouched | PASS |
| py_compile passes | PASS |

## Gate position
Added after `max_per_market` gate — correctly grouped with concurrency controls, before cooldown and market validity checks.

## Restart required: YES
