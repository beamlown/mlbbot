# HANDOFF: MLB_CONFIDENCE_CALIBRATION_AUDIT_001

## What you are doing
Read-only audit of whether the current MLB confidence score means anything trustworthy.

## Goal
Determine whether confidence is calibrated, inverted, noisy, or structurally invalid against real outcomes.

## Deliver back
- calibration verdict
- bucket evidence
- contamination caveats
- recommendation on whether confidence should be rescaled, retrained, replaced, or redefined

## Do not do
- no code edits
- no retraining
- no runtime changes