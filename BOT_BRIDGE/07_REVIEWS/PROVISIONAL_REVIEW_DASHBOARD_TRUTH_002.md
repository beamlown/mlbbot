# PROVISIONAL REVIEW — DASHBOARD_TRUTH_002

Decision: APPROVED_PENDING_CLAUDE

## Subsystem

`dashboard_truth_layer`

## Provisional review summary

This is the correct next task.

The incident/debug work established that execution truth is now trustworthy enough to use as the primary user-facing layer again. The dashboard still carries remnants of mixed truth sources across:
- DB/open trades
- runtime state
- shadow/advisory enrichment

The next task is appropriately narrow because it does **not** require:
- model redesign
- execution redesign
- dashboard visual redesign from scratch
- new incident handling

It only requires tightening truth ownership between `dashboard_server.py` and `dashboard.html` so the UI presents one coherent assembly line.

## Expected source-of-truth policy

- **Primary user-facing positions**: paper execution truth only
- **Top-level open counts/KPIs**: paper execution truth only (with runtime state used as telemetry, not competing truth)
- **Shadow/advisory**: diagnostics only

## Likely implementation files

- `dashboard.html`
- `dashboard_server.py`

## Why approved provisionally

The task is:
- focused
- bounded
- aligned with current architecture
- the right follow-up after containment and state resync

## Decision

APPROVED_PENDING_CLAUDE
