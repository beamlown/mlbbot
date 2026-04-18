# HANDOFF: MLB_DAILY_PREV_DAY_UPDATER_BUILD_001

## Status: QUEUED — reassigned to SONNET_WORKER (HAIKU_WORKER failed to produce output on two prior attempts)

## What you are doing
Build the daily previous-day MLB ingestion path after the stats foundation spec and season backfill are complete.

## Goal
Keep the canonical MLB raw stats store current by appending the prior day’s completed games safely and idempotently.

## Scope
Updater only. Same canonical store. No broader scheduling or model logic work.

## Deliver back
- files changed
- append target path
- idempotency behavior
- compatibility with backfill output

## Do not do
- no model/recommendation changes
- no storage redesign
- no broad platform/scheduler work beyond the ingestion path