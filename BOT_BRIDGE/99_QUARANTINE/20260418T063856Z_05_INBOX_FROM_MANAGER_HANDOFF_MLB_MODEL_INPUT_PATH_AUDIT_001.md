# HANDOFF: MLB_MODEL_INPUT_PATH_AUDIT_001

## What you are doing
Read-only trace of what the current MLB model actually sees and what reaches the recommendation layer.

## Goal
Answer, precisely:
- what are the real model inputs
- what game-state and market-state context survives to recommendation output
- what expected context is missing, compressed, or dropped

## Scope
Stay inside the recommendation / feature / bridge path only.
Do not widen into strategy tuning or code changes.

## Deliver back
- exact feature list
- exact source-to-output path
- missing context list
- distinction between model input and post-model metadata

## Do not do
- no code edits
- no training
- no backfill
- no repo-wide sweep outside the model input path