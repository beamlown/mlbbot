# HANDOFF - VERIFY_ODDS_API_BUDGET_ENFORCEMENT_001
## Verify Odds API daily/monthly budget enforcement with isolated proof states

Current budget logic under proof:
- daily hard cap: `600`
- monthly soft target: `18000`
- monthly hard cap: `20000`
- tracked budget fields:
  - `date`
  - `count`
  - `month`
  - `month_count`
  - `mode`

Mode thresholds:
- `< 18000/month` -> `normal`
- `>= 18000/month and < 20000/month` -> `soft_throttle`
- `>= 20000/month` -> `hard_stop`
- `>= 600/day` always blocks non-essential calls for the rest of the day

Safe proof method:
- use helper script `C:\Users\johnny\Desktop\BOT_BRIDGE\proof_verify_odds_budget_001.py`
- point `ODDS_BUDGET_PATH` to an isolated temp budget file
- call current `_check_and_increment_budget()` logic directly
- do not make real Odds API requests
- do not mutate the live runtime budget file

Additional verification:
- confirm live dashboard/realtime path remains independent of Odds API streaming
