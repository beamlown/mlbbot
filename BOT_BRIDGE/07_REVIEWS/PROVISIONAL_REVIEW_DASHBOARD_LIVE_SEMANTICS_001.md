# PROVISIONAL_REVIEW_DASHBOARD_LIVE_SEMANTICS_001

Decision: PROVISIONALLY_APPROVED

## What changed

This was a frontend-only semantics cleanup, not a math/backend change.

### Before
- held-side label used ambiguous `WIN / LOSE`
- `Current` price label did not make held-side semantics obvious
- stale/unavailable market state was too easy to miss
- cash strip labels were technically correct but not immediate enough

### After
- held-side text now reads explicitly as `TEAM TO WIN` or `TEAM TO LOSE`
- contract badge now reads `YES CONTRACT` / `NO CONTRACT`
- lifecycle status remains separate in the status badge
- price label now reads:
  - `Held price now`
  - `Held price (stale)`
  - `Held price unavailable`
- stale/unavailable note explicitly warns that live P&L and live equity may lag or be incomplete
- cash strip labels now explain the accounting relationship more clearly

## What did not change

- current price formula
- unrealized P&L formula
- live equity formula
- backend available cash / committed capital math
- model logic
- strategy logic

## Why backend change was not needed

The underlying formulas were already mostly correct. The user-facing problem was semantic ambiguity, not missing backend fields.

## Conclusion

This should make live cards materially easier to interpret without risking truth regression.
