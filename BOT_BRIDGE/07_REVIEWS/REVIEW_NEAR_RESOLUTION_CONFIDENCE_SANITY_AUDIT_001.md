# REVIEW_NEAR_RESOLUTION_CONFIDENCE_SANITY_AUDIT_001.md

## Verdict
APPROVED — PARTIAL PASS (read-only audit, no fix implemented by design)

## Decision
Approve `NEAR_RESOLUTION_CONFIDENCE_SANITY_AUDIT_001`. Move to DONE. Open new model-side task `NEAR_RESOLUTION_CONFIDENCE_SUPPRESSOR_001` to implement the medium-term fix.

## What was confirmed

- Root cause correctly classified as **Type B**: model receives market price as input (for edge computation) but the confidence formula does not penalize extreme market prices. The formula `confidence = edge_score × data_quality × spread_quality` is actually MAXIMIZED by near-resolution markets because a large price discrepancy (e.g., model says 55% for a market priced at 0.01) produces a massive edge, which clamps edge_score to 1.0.

- Near-resolution suppressor gap in `risk.py` correctly identified:
  - Existing `near_resolution_entry` gate (lines 198-201): catches `bid >= NEAR_RESOLUTION_PRICE (0.92)` — protects the winning side.
  - Does NOT catch the losing-side near-zero case (e.g., BUY_YES at 0.01).
  - `MIN_ENTRY_PRICE=0.22` IS the correct circuit breaker for the losing-side case. It is already applied and awaits cold restart.

- Confidence formula location confirmed: `recommendation_api.py` line 207.

- Bridge-layer game_state_age check confirmed: 60s window in `model_bridge.py`.

- No files modified — correct for a read-only audit.

## Why this matters

Even after MIN_ENTRY_PRICE=0.22 is enforced, the model will continue to produce misleading high-confidence recommendations for near-resolved markets (confidence 0.55+ on a 0.01 market). These recs get logged in shadow recommendations and could mislead future analysis. The model-side fix is worth doing.

## Recommended follow-on task

**`NEAR_RESOLUTION_CONFIDENCE_SUPPRESSOR_001`** — In `recommendation_api.py`, add a post-inference confidence suppressor: when `market.p_cost_yes < 0.10` (for BUY_YES) or `market.p_cost_no < 0.10` (for BUY_NO), cap confidence at 0.0 and set action to `NO_TRADE`. This is an mlb_model file — requires a model-side task brief. Add to BACKLOG.

## Manager judgment

Close `NEAR_RESOLUTION_CONFIDENCE_SANITY_AUDIT_001` to DONE.
Add `NEAR_RESOLUTION_CONFIDENCE_SUPPRESSOR_001` to BACKLOG (model-side task).
