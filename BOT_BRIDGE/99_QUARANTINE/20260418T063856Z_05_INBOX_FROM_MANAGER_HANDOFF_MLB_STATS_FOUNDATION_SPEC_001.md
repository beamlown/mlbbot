# HANDOFF: MLB_STATS_FOUNDATION_SPEC_001

## What you are doing
Produce the canonical MLB season data foundation spec that all later build work must follow.

## Goal
Remove guessing before code-writing tasks begin.
The output should define:
- canonical raw storage path
- normalized/rebuild-ready storage path
- required entities
- required vs optional fields
- file format and partitioning
- versioning and refresh rules
- season-to-date completeness definition
- daily updater append/idempotency rules

## Scope
Spec only. No code changes. No data writes. No downloads.

## Deliver back
- final spec artifact path
- raw vs normalized storage decision
- required entities and fields
- completeness definition
- updater safety/idempotency rules

## Do not do
- no backfill code
- no updater code
- no model changes
- no speculative feature design beyond storage/schema needs