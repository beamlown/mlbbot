# HANDOFF: MARKET_PRICE_SANITY_GATE_001

## What you are doing
Add one distinct hard sanity gate for obviously irrational extreme-price entries.

## Why this exists
Near-zero and near-one markets need explicit future handling. The simple min entry price floor is not sufficient to represent the whole problem.

## Scope
Keep this narrow and gate-focused. Distinct from the broader near-resolution audit.

## Deliver back
- files changed
- exact gate logic summary
- env vars added or reused
- exact rejection reason
- py_compile results
- restart note

## Do not do
- no model rewrite
- no broad risk rewrite
- no dashboard work
- no repo sweep