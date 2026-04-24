# HANDOFF — DASH_014
## Win rate for paper trades + fix BUY_NO TP/SL

---

## ✅ STATUS: ACTIVE — proceed immediately.

---

## Context

Two bugs in `dashboard_server.py`:

1. **Win rate never computed** — the dashboard KPI strip already has a `kpi-winrate` element that reads `s.r25.win_rate`, but `/api/state` never returns an `r25` field. The KPI always shows "—". We need to query the DB and attach the result.

2. **BUY_NO TP is wrong** — `_fetch_trades()` has `tp_price = 0.85` hardcoded for all sides. For a BUY_YES position, 0.85 is correct (YES price rises to 0.85 → we win). For a BUY_NO position, 0.85 is a *losing* YES price — the NO contract loses value when YES goes up. The correct TP for BUY_NO is a *low* YES price: `max(0.01, 1.0 - entry_px * (1 + 0.85))`.

**Do NOT touch**: `dashboard.html`, `launch_all.py`, `bot_core.py`, `core/paper_exec.py`, `.env`, `core/`, `mlb_model/`

---

## Fix 1 — Add r25 to _read_state()

Find `_read_state()` in `dashboard_server.py`. After building the bankroll dict (the block that queries `SELECT SUM(pnl_usd) FROM trades`), add:

```python
rows = conn.execute(
    "SELECT pnl_usd FROM trades WHERE status='closed' ORDER BY id DESC LIMIT 25"
).fetchall()
wins   = sum(1 for r in rows if (r["pnl_usd"] or 0) > 0)
losses = sum(1 for r in rows if (r["pnl_usd"] or 0) <= 0)
total  = len(rows)
win_rate = round(wins / total, 4) if total else None
exp      = round(sum((r["pnl_usd"] or 0) for r in rows) / total, 4) if total else None
state["r25"] = {
    "win_rate":   win_rate,
    "wins":       wins,
    "losses":     losses,
    "expectancy": exp,
    "sample_size": total,
}
```

The `conn` variable is already in scope inside `_read_state()`. The `state` dict is what gets returned as JSON. This change adds one more key to it.

---

## Fix 2 — Side-aware TP/SL in _fetch_trades()

**Step A** — At module level near the other `os.getenv` calls, add:

```python
AUTO_TAKE_PROFIT_PCT = float(os.getenv("AUTO_TAKE_PROFIT_PCT", "0.85"))
AUTO_STOP_LOSS_PCT   = float(os.getenv("AUTO_STOP_LOSS_PCT",   "0.20"))
```

**Step B** — In `_fetch_trades()`, find the existing hardcoded block (looks like `tp_price = 0.85` and the sl computation). Replace it entirely with:

```python
if side == "BUY_NO":
    tp_price = round(max(0.01, 1.0 - entry_px * (1 + AUTO_TAKE_PROFIT_PCT)), 6)
    sl_price = round(min(0.99, entry_px * (1 + AUTO_STOP_LOSS_PCT)), 6)
else:  # BUY_YES
    tp_price = round(min(0.99, entry_px * (1 + AUTO_TAKE_PROFIT_PCT)), 6)
    sl_price = round(max(0.01, entry_px * (1 - AUTO_STOP_LOSS_PCT)), 6)
```

**Example sanity check** — for a BUY_NO with entry_px=0.41:
- tp_price = max(0.01, 1.0 - 0.41 * 1.85) = max(0.01, 0.2415) = **0.2415** ✓ (low YES price = NO wins)
- sl_price = min(0.99, 0.41 * 1.20) = min(0.99, 0.492) = **0.492** ✓ (YES rising past entry = NO losing)

---

## Verification

```
curl http://localhost:8900/api/state
```
Look for `"r25": {"win_rate": ..., "wins": ..., "losses": ..., "expectancy": ..., "sample_size": ...}` in the JSON.

```
curl http://localhost:8900/api/trades
```
Find a BUY_NO trade (side = "BUY_NO"). Its `tp_price` should be **below 0.50**, not 0.85.

If there are no closed trades, `r25.win_rate` must be `null` — not an error.

---

## Rollback

Revert `dashboard_server.py` only.
