# HANDOFF_CONFIDENCE_GATE_RUNTIME_VERSION_TRACE_001.md

## Task
`CONFIDENCE_GATE_RUNTIME_VERSION_TRACE_001`

## Goal
Prove what code/process/version actually produced the low-confidence live opens.

## Why this exists
The last trace ruled out an obvious second current on-disk open path in the scoped bridge code.
That means the remaining likely explanation is runtime divergence:
- stale bytecode
- wrong process
- wrong working tree/path
- or another runtime-version identity mismatch

## Read-only only
Do not modify code.
Do not restart processes.
Do not widen scope unless needed to prove process/path identity.

## Core question
What exactly was running when trades 241 / 243 / 244 opened?

## Required approach
- trace startup/restart evidence around those trades
- inspect current source vs runtime evidence
- inspect pycache metadata only if present and useful
- inspect launcher/process-path evidence only if needed and justify it

## Result
Write:
`06_OUTBOX_FROM_WORKER/RESULT_CONFIDENCE_GATE_RUNTIME_VERSION_TRACE_001.json`
