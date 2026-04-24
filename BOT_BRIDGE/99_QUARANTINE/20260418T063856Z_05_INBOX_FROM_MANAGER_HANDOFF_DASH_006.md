# HANDOFF — DASH_006
## Fix TP/SL — compute server-side per trade in /api/trades

---

## Context

Position cards use `tp_price` and `sl_price` from the trade object. These values currently come from hardcoded JS constants on the frontend. This task adds server-side computation so the values are returned from `/api/trades` directly. The frontend constant removal is a separate task (DASH_008).

---

## File to change

`sports_bot_v2/dashboard_server.py` — ONLY this file.

---

## Change

In `_fetch_trades()` (around line 233), find the block that builds each trade dict in the `result.append({...})` call. After the existing fields, add tp_price and sl_price for non-manual trades.

**Find the result.append block for bot/model_bridge rows. It looks like:**
```python
result.append({
    "id": r["id"], "ts_open": r["ts_open"], ...
    "source": r["source"] or "bot",
})
```

**Add these two lines inside that dict (before the closing `}`):**
```python
                "tp_price": 0.85,
                "sl_price": round((r["entry_px"] or 0.0) * 0.80, 4) if (r["side"] or "") == "BUY_YES" else round(min((r["entry_px"] or 0.0) * 1.20, 0.99), 4),
```

Do NOT add these fields to the manual_trades block below it.

---

## Verification

```
cd C:\Users\johnny\Desktop\sports_bot_v2
python dashboard_server.py
```

Second terminal:
```
curl http://localhost:8900/api/trades
```

Each non-manual trade must have `"tp_price": 0.85` and a `sl_price`. For a BUY_YES trade with `entry_px: 0.60`, `sl_price` must be `0.48`.

## Rollback

Revert `dashboard_server.py` only.
