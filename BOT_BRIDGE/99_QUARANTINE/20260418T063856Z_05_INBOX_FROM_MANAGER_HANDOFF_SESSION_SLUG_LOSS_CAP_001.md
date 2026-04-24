# HANDOFF: SESSION_SLUG_LOSS_CAP_001

## What you are doing
Add a per-session dollar-loss cap per slug so one toxic market can be banned before count-only rules are exhausted.

## Why this exists
Repeated-market damage can become severe even when a simple trade-count cap exists. We need a dollar-loss containment layer.

## Scope
Keep this narrow and gate-focused. Do not redesign exits or the broader risk system.

## Deliver back
- files changed
- env var name and default
- exact rejection reason
- where slug loss is computed
- py_compile results
- restart note

## Do not do
- no broad risk refactor
- no dashboard work
- no model work
- no repo sweep