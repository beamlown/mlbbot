# HANDOFF: MLB_CURRENT_SEASON_BACKFILL_BUILD_001

## What you are doing
Build the season-to-date MLB backfill path after the stats foundation spec is finalized.

## Goal
Populate the canonical raw season store with completed MLB games for the current season so far.

## Scope
Narrow backfill only.
Use the approved spec. Do not redesign storage during implementation.

## Deliver back
- files changed
- raw destination path
- coverage achieved
- rerun/idempotency behavior

## Do not do
- no updater logic in this task
- no recommendation/model changes
- no storage redesign