# HANDOFF - ODDS_API_BUDGET_ENFORCEMENT_001
## Enforce daily and monthly Odds API budget policy without live-stream dependence

Current Odds API use:
- `sports_bot_v2\sports\mlb\sharp_odds.py`
- used for MLB cross-book / sharp-odds verification inputs
- not part of dashboard SSE/live-stream path

Current tracking:
- `runtime/odds_budget.json` exists and tracks daily usage
- `.env` already sets `MAX_ODDS_CALLS_PER_DAY=600`
- live log evidence already showed `odds_budget: daily limit 600 reached`

What current code already did:
- enforced a real daily hard cap
- tracked daily usage count

Real missing piece:
- explicit monthly soft-target pacing (`18000/month`)
- explicit monthly hard-cap awareness (`20000/month`)

Smallest safe fix applied:
- extend the existing budget state to track:
  - `month`
  - `month_count`
  - `mode` (`normal` / `soft_throttle` / `hard_stop`)
- keep daily hard cap at `600`
- add monthly soft ceiling target at `18000`
- add monthly hard cap awareness at `20000`
- when monthly soft ceiling is exceeded, automatically skip some non-essential fetches via throttle mode
- when monthly hard cap is reached, stop non-essential fetches entirely

Important:
- Odds API remains verification-only and non-streaming
- live dashboard remains independent of Odds API freshness for primary motion

Rollback:
- Revert the narrow budget-enforcement changes in `sports/mlb/sharp_odds.py`
