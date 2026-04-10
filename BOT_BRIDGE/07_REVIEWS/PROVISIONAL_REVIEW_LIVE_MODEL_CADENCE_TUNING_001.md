# PROVISIONAL_REVIEW_LIVE_MODEL_CADENCE_TUNING_001

Decision: PROVISIONALLY_APPROVED

## What changed
- `RECOMMENDATION_LOOP_SECONDS` default changed from `30` to `15`
- `GAME_STATE_CACHE_TTL` default changed from `15` to `8`
- `BOOK_CACHE_TTL` stayed at `5`

## Why this is acceptable
- this tightens the two coarsest cadence layers first
- it does not redesign strategy
- it does not retrain the model
- it does not claim fake ultra-fast behavior
- it avoids the riskiest API-burn increase by leaving book-cache cadence unchanged

## What remains true
- live recommendation cadence is tighter than before
- no unnecessary Odds API increase was introduced
- no production files outside the allowed set were changed

## Exact old vs new values
- recommendation loop: `30s` -> `15s`
- game-state cache TTL: `15s` -> `8s`
- book cache TTL: `5s` -> `5s`

## Conclusion
This is the smallest safe first-step improvement and satisfies the requested narrow cadence-tuning scope.
