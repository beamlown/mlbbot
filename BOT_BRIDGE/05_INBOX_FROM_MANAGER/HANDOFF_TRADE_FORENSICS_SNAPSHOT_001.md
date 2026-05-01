# HANDOFF: TRADE_FORENSICS_SNAPSHOT_001

## What you are doing
Add a compact per-trade forensic snapshot so each new entry carries enough context for later audit and replay.

## Why this exists
Right now trade forensics are too weak. When a bad trade opens, we cannot cleanly reconstruct why it passed and what runtime/config context was active.

## Required fields
- confidence
- entry price
- side
- slug
- mode
- gate pass context
- game-state context if available
- config version/hash at entry

## Scope
Keep this narrow. Use the smallest existing persistence path that works. Do not redesign storage.

## Deliver back
- files changed
- exact snapshot schema
- where it is persisted
- py_compile results
- restart note

## Do not do
- no dashboard work
- no broad logging overhaul
- no model changes
- no speculative schema redesign