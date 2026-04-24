# HANDOFF_POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001.md

## Task
`POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001`

## Goal
Find out why the live dashboard is sometimes showing the bot as backing the wrong team.

## Read-only only
Do not modify code.
Do not restart processes.
Do not widen scope.

## What is already known
- The operator is seeing a live mismatch between the true backed side and the dashboard wording.
- Similar semantics issues have existed before in this system.

## Your job
Take one or more current live positions and trace:
execution truth -> runtime/state truth -> dashboard_server payload -> dashboard.html labeling

Then identify exactly where the mismatch is introduced.

## Result
Write:
`06_OUTBOX_FROM_WORKER/RESULT_POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001.json`
