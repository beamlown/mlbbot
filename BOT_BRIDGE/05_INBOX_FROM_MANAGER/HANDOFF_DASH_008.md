# HANDOFF — DASH_008
## Remove hardcoded TP/SL JS constants from dashboard.html

---

## Context

DASH_006 added `tp_price` and `sl_price` to the `/api/trades` response. The position card builder already reads `r.tp_price` and `r.sl_price` from the trade object. The two JS constants that previously provided fallback values are now redundant and should be deleted.

**Prerequisite:** DASH_006 must be complete and approved before running this.

---

## File to change

`sports_bot_v2/dashboard.html` — ONLY this file.

---

## Change

Find and delete these two lines (near line 738, exact line numbers may have shifted from prior edits):

```javascript
const TP_PRICE = 0.85; // matches AUTO_TAKE_PROFIT_PCT
const SL_PCT   = 0.20; // matches AUTO_STOP_LOSS_PCT
```

Delete both lines entirely. Do not replace them with anything.

Before deleting, search the rest of the file for any reference to `TP_PRICE` or `SL_PCT` as standalone variables. If any other code still references them, note it in the result — do not delete the lines until all references are handled. (Expected: no other references, since the card builder uses `r.tp_price` / `r.sl_price` directly.)

---

## Verification

```
cd C:\Users\johnny\Desktop\sports_bot_v2
python dashboard_server.py
```

Then in a second terminal:
```
grep -n "TP_PRICE\|SL_PCT" dashboard.html
```

Must return no matches.

## Rollback

Revert `dashboard.html` only.
