# HANDOFF — SYSTEM_BUG_AUDIT_001

## Mode
Read-only audit only. No production code changes. No redesign. No service restarts unless required for hard-failure verification.

## Goal
Audit the current end-to-end bot system and identify what is actually broken, misleading, stale, risky, or likely to break soon.

## Audit categories
1. Process topology / runtime health
2. Data truth / API consistency
3. Trade/accounting semantics
4. Dashboard truth / usability
5. Live game monitor quality
6. Bridge / recommendation / execution path
7. BOT_BRIDGE workflow hygiene

## Required deliverables
- RESULT_SYSTEM_BUG_AUDIT_001.json
- PROVISIONAL_REVIEW_SYSTEM_BUG_AUDIT_001.md
- updates to SESSION_JOURNAL.md, STATE_OF_SYSTEM.md, CLAUDE_CATCHUP_BRIEF.md

## Output requirements
Result must include:
1. CURRENTLY HEALTHY
2. CRITICAL BUGS
3. IMPORTANT BUGS
4. COSMETIC / LATER ISSUES
5. LIKELY ROOT CAUSES
6. EXACT FILES OR SUBSYSTEMS INVOLVED
7. WHAT SHOULD BE FIXED FIRST
8. WHAT MUST NOT REGRESS

## Tone
Be blunt. Include evidence. If something is unverified, label it unverified.
