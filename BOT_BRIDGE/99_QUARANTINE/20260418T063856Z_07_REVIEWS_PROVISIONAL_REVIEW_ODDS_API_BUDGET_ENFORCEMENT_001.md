# PROVISIONAL_REVIEW_ODDS_API_BUDGET_ENFORCEMENT_001

Decision: PROVISIONALLY_APPROVED

## What was already true

- Odds API was already non-streaming.
- It is used through `sports/mlb/sharp_odds.py`, not through dashboard SSE/live motion.
- Daily usage was already tracked in `runtime/odds_budget.json`.
- Daily hard-cap enforcement was already real, with `.env` set to `MAX_ODDS_CALLS_PER_DAY=600` and live logs proving cap-hit behavior.

## What was missing

- explicit monthly soft-target pacing at `18000/month`
- explicit monthly hard-cap awareness at `20000/month`

## What changed

A narrow extension was added to `sports/mlb/sharp_odds.py`:
- budget state now tracks:
  - `month`
  - `month_count`
  - `mode`
- monthly modes:
  - `normal`
  - `soft_throttle`
  - `hard_stop`
- behavior:
  - `600/day` -> stop non-essential Odds API calls for the rest of the day
  - `18000/month+` -> automatically throttle non-essential fetches
  - `20000/month+` -> stop non-essential fetches entirely

## Why this fits the architecture rule

- Polymarket/live dashboard path can stay realtime
- Odds API remains low-frequency and verification-only
- no Odds API streaming was introduced
- live dashboard still does not depend on Odds API freshness for primary motion

## Scope check

- no strategy redesign
- no model retraining
- no widening of scope
- no execution-path redesign

## Conclusion

This is the right narrow enforcement step. Daily cap is now aligned with the stated 600/day rule, and monthly pacing/hard-cap awareness are explicitly enforced.
