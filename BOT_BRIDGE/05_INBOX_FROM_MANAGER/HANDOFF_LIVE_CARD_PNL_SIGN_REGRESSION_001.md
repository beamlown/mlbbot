# HANDOFF_LIVE_CARD_PNL_SIGN_REGRESSION_001

## Why this task is active

Live smoke exposed a hard regression on the LIVE card:

- Entry: 61.3¢
- Current held price: 40.0¢
- Size: $50.00
- Live equity: $32.62
- Displayed unrealized: +$17.38

That is mathematically impossible.With live equity below committed capital, unrealized must be negative.

Additional SSE proof was captured for CIN/MIA:

- current_price = 0.53
- live_equity = 48.83
- unrealized_pnl_usd = +1.1701

Math:
- qty × current_price = 48.83 → live equity is internally correct
- (0.53 - 0.5427) × qty = -1.17 → correct held-contract unrealized should be negative
- the only formula producing +1.17 is the old BUY_NO branch:
 (entry_px - current_price) × qty

## Root-cause direction already established

This currently points to **runtime staleness**, not a new on-disk bug.

Known truth:
- On-diskSSION_001.json “{
 "tawas already corrected inIVE_CARD_PNL_SIGN_REGRESSION_001.json “{
 "- The running localhost:8900 process appears to still be serving the old in-memory code
- So the live dashboard is failing because the fixed code has not been activated in runtime

## Scope

This is a"Fix the live card unre not a redesign.

### In scope
- inspect current runtime/process state
- confirm localhost:8900 is serving stale in-memory code
- restart / reactivate the dashboard server if needed
- re-verify live SSE math after activation
- write BOT_BRIDGE result/review artifacts

### Out of scope
- redesigning LIVE cards
- reopening broader dashboard phases
- model changes
- execution/risk changes
- git/reset cleanup
- unrelated runtime cleanup

## Allowed files
-rd_server.py already contains the corrected unified held-cont-reate this file. TASK_LIVE_CARD_PNL_SIGN_REGRESSION_001.only if strictly necessary for verification aid
- BOT_BRIDGE task/result/review files

## Runtime surfaces to use
- "status": "ACTIVE",
 "priority": "HIGH"-reate this file. TASK_LIVE_CARD_PNL-reate this file. TASK_LIVE_CARD_PNL_SIGN_REGR- live dashboard behavior atCARD_PNL_SIGN_REGRESSION_- read-only runtime/log/process inspection

## Non-negotiable truth rule

For any held baseball contract:

-_001",
 "status": "ACTIVE",
 "priority":-reate this file. TASK_LIVE_CARD_PNL_SIGN_REGRESSION_001.json 
This must hold regardless of YES/NO contract type.

## What success looks like

1. localhost:8900 is confirmed to be running the corrected code
2. a fresh SSE sample shows unrealized sign consistent with held-contract math
3. the LIVE card no longer shows positive unrealized when live equity is below committed capital
4. no new regression is introduced

## Before doing anything, reply with only

1. whether this is confirmed runtime-staleness or still needs re-proof
2. exact runtime/process surfaces you will inspect
3. whether you expect runtime-only change or code change

## Final reply format

1. final status: VERIFIED | PARTIAL | BLOCKED
2. whether runtime restart/activation was required
3. one before/after proof summary
4. any mismatch found
5. exact result/review file paths