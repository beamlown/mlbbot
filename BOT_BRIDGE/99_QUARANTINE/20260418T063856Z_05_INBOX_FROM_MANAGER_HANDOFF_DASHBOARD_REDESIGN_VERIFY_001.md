# HANDOFF_DASHBOARD_REDESIGN_VERIFY_001

## Status: HOLD_PENDING_EXECUTION_TRUTH

**Do not begin until:** `DASHBOARD_PERFORMANCE_POLISH_001` APPROVED.

---

## What this task is

Phase 5 of the redesign. **Read-only verification. Zero code changes.**

You are verifying that the redesigned dashboard preserves the truth model and that the known incidents cannot recur in the display layer.

---

## Critical checks — these map directly to the known incidents

### SEA/TEX incident re-check (BUY_NO pricing)
```
BUY_NO position, ob.bid_no = 0.62, entry_px = 0.41
Expected: current_held_price = 0.62 (bid_no)
Expected: unrealized_pct = (0.62 - 0.41) / 0.41 = +0.512 (positive — profit)
FAIL if: current_held_price = 1 - 0.62 = 0.38 (wrong — bid_yes of NO contract)
FAIL if: unrealized_pct is negative when bid_no > entry_px
```

### BOS/MIL incident re-check (close pricing)
```
BUY_NO closed trade in HISTORY/POSITIONS tab
Expected: exit_px is a NO-side price (typically 0.5-0.99 range for a won bet)
FAIL if: exit_px shows YES-side price for a BUY_NO close
```

### Shadow exclusion
```
Open LIVE tab → confirm no advisory/shadow section visible
Open GAMES tab → confirm advisory section has 'Advisory' label and muted styling
```

---

## Output

Write result JSON to:
```
C:/Users/johnny/Desktop/BOT_BRIDGE/06_OUTBOX_FROM_WORKER/RESULT_DASHBOARD_REDESIGN_VERIFY_001.json
```

Include per-check pass/fail with observed values. Include explicit incident re-verification statements.

---

## Deliverable check

- [ ] Result JSON written to 06_OUTBOX_FROM_WORKER
- [ ] BUY_NO price check: explicit pass/fail with observed bid_no value
- [ ] Unrealized sign check: explicit pass/fail
- [ ] Shadow exclusion check: explicit pass/fail
- [ ] STALE badge behavior confirmed
- [ ] JS error check: zero errors confirmed
- [ ] Zero production file changes
