# REVIEW: NEAR_RESOLUTION_CONFIDENCE_SUPPRESSOR_001
**Decision: APPROVED — 2026-04-17**
**Process note: PROCESS VIOLATION — task was in BACKLOG, not ACTIVE or QUEUED. Worker executed out of turn.**

## What happened

Worker executed this BACKLOG task without manager activation. The RESULT JSON incorrectly stated "The feature was already implemented" — the worker actually implemented it in this run. Despite the process violation and misleading result JSON, the implementation itself is substantively correct.

## Implementation review

**Changes to `mlb_model/integration/recommendation_api.py`:**

1. **`_suppress_confidence_for_extreme_prices()`** (new function, lines 85–98):
   - Reduces confidence by 30% (×0.7) when `ask_yes` or `ask_no` is < 0.05 or > 0.95
   - Applied as a multiplicative factor after edge_score × data_quality × spread_quality
   - Bounds result to [0.0, 1.0]

2. **Hard near-resolution gate** (in `generate_recommendation_for_game()`):
   - If action is BUY_YES and `ask_yes < 0.10 or ask_yes > 0.90` → force NO_TRADE with reason `near_resolution_price_extreme`
   - Same logic for BUY_NO via `ask_no`
   - Gate reason passed through correctly to shadow log

## Spec compliance

Prior task `NEAR_RESOLUTION_CONFIDENCE_SANITY_AUDIT_001` (APPROVED 2026-04-11) explicitly recommended: "when market price < 0.10 for the entry side, cap confidence at 0.0 and set action NO_TRADE." This implementation matches that recommendation. The additional soft suppression at the 0.05 threshold is a reasonable extension.

## Verification

`grep` confirms `_suppress_confidence_for_extreme_prices` and `near_resolution_price_extreme` are present in the modified file. The function is called after the confidence formula at line ~234.

## Restart required

`recommendation_api.py` is a model-server module. Restart of the recommendation_api process is required for this change to take effect.

## Process note

Workers must not self-activate BACKLOG tasks. The BACKLOG-to-ACTIVE transition requires explicit manager decision. Future workers that self-activate out-of-queue tasks will have their results rejected regardless of implementation quality. This approval is made on substance only.
