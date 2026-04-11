# OPERATOR ACTION REQUIRED — CRITICAL
## Last updated: 2026-04-11
## Status: UNRESOLVED — bot is currently running with broken gate

---

## DO THIS BEFORE ANY CODE FIX HAS MEANING

The confidence gate patch exists in `bot_core.py` source but is **not being executed** because Python is loading pre-patch bytecode from `__pycache__`. Every restart since 18:41 CDT on 2026-04-10 has loaded stale bytecode.

**Until the pyc file is deleted and the bot is cold-restarted, ALL of the following are broken:**
- Confidence floor (0.60) is not enforced
- Market cooldown checks are not reached (gate path is bypassed)
- All risk gates inside `check_entry_gates()` are not running

**Evidence:** 31 of 42 trades tonight (73.8%) were sub-0.60. Session closed at -$159.54.

---

## Step-by-step operator action

**Step 1 — Stop the bot**
Shut down `bot_core.py` cleanly via the launcher or directly.

**Step 2 — Delete the stale pyc file**
```
del "C:\Users\johnny\Desktop\sports_bot_v2\__pycache__\bot_core.cpython-*.pyc"
```
Or from bash:
```bash
rm C:/Users/johnny/Desktop/sports_bot_v2/__pycache__/bot_core.cpython-*.pyc
```

**Step 3 — Cold restart**
Restart the full stack via `launch_all.py` (do not just restart bot_core — let the launcher sequence properly).

**Step 4 — Verify gate is active**
Watch bot log for:
```
BRIDGE GATE REJECT [check_entry_gates] slug=... reasons=['confidence_too_low:...]
```
This must appear before any sub-0.60 intent is allowed to open a trade.

**Step 5 — Do not trust gate/cooldown behavior until Step 4 is confirmed.**

---

## What this does NOT fix (separate code tasks pending)

| Gap | Fix Task |
|-----|----------|
| Ultra-low-price entries (instant SL at 5–7 cents) | MIN_ENTRY_PRICE_GATE_001 |
| TP unreachable for near-1.0 entries | TP_NEAR_RESOLUTION_CAP_FIX_001 |
| Cooldown wiped on restart | MARKET_COOLDOWN_PERSIST_001 |
| Duplicate-intent bypass in bridge loop | BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001 |

---

## This item stays open until Johnny confirms pyc was deleted and gate is verified active.
