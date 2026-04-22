# HANDOFF: GAME_STATE_FRESHNESS_AUDIT_001

## What you are doing
Read-only audit of whether recommendation-time game-state is fresh enough to trust.

## Why this exists
We still do not know whether irrational late-game recommendations come from stale, missing, or insufficient score/inning/outs/base-state data.

## Scope
Read only the narrow recommendation path.
Classify score, inning, outs, and base-state separately.

## Deliver back
- exact code regions inspected
- freshness or lag signals found
- field-by-field classification
- one-paragraph recommendation

## Do not do
- no code edits
- no broad repo sweep
- no bot_core work
- no dashboard work