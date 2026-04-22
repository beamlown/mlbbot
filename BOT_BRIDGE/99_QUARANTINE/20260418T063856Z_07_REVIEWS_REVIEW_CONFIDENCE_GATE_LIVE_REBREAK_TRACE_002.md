# REVIEW_CONFIDENCE_GATE_LIVE_REBREAK_TRACE_002.md
**Decision: APPROVED (confirmed) — 2026-04-17**

## Verdict
APPROVED

## Decision
Approve `CONFIDENCE_GATE_LIVE_REBREAK_TRACE_002`.

## Why
- The worker stayed read-only and within the intent of the task.
- The worker proved an important narrowing:
  - within the allowed scoped code, there is only one current visible bridge `open_position(...)` path
  - that path already appears correctly guarded by `check_entry_gates()` with reject + immediate `continue`
- That means the previous live sub-0.60 opens are **not** explained by an obvious second current on-disk open path in the scoped files.

## Key conclusion
The most likely remaining explanation is **runtime divergence / stale running code / version traceability failure**, not a safe in-scope code patch in the currently inspected bridge path.

## What this rules out
- A blind patch to the current visible reject-and-continue branch in `bot_core.py`
- A blind assumption that the current on-disk logic is the same logic that produced trades 241 / 243 / 244

## Manager judgment
Open a new high-priority read-only task:

`CONFIDENCE_GATE_RUNTIME_VERSION_TRACE_001`

Purpose:
- prove exactly what code/process/version/path was running when the low-confidence trades opened
- determine whether stale bytecode, wrong process, wrong working tree, or another runtime-version mismatch explains the live rebreak

## Priority
Keep `POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001` queued behind the runtime/version trace.
The confidence-gate runtime divergence issue is still the higher-risk live trading problem.
