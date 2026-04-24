# HANDOFF — MIN_ENTRY_PRICE_GATE_001
**Priority:** CRITICAL
**Type:** Code fix — narrow, single-gate addition
**Issued:** 2026-04-11
**Scope:** NARROW — one gate condition added to `check_entry_gates()` in `core/risk.py` only. Do not touch other gates, do not refactor.

---

## One-sentence task

Add a hard minimum entry price gate in `check_entry_gates()` that blocks entries when the ask price for the intended side is below a configurable floor (default 0.15), preventing the bot from entering ultra-low-price markets where the bid-ask spread already exceeds the stop-loss threshold.

---

## Why this exists

Tonight's audit (2026-04-11) found 7 trades entered at 0.05–0.07 ask price, all stopped out in 1–2 seconds with losses of $10–12 each. At these prices, the market's own bid-ask spread (~15–21%) exceeds the 12% SL threshold. The position is underwater before the first loop check runs.

The existing `spread_too_wide` gate operates on absolute spread value, not spread-relative-to-price. A 1-cent spread on a 6-cent market passes the absolute check but is a 17% relative spread. The minimum price gate is the cleanest fix.

**Confirmed evidence:**

| Trade | Entry | Exit | Duration | Relative spread |
|-------|-------|------|----------|----------------|
| #232 | 0.07035 | 0.0597 | 1s | ~15% |
| #248 | 0.06030 | 0.04975 | 1s | ~18% |
| #255 | 0.05025 | 0.03980 | 2s | ~21% |

---

## What you must NOT do

- Edit any other gate logic in `check_entry_gates()`
- Change the ordering of existing gates
- Touch `.env` unless strictly necessary to add the env-var read
- Touch `bot_core.py`, `dashboard_server.py`, `dashboard.html`
- Add logging beyond a single gate-reject log line (existing pattern)
- Add tests or docstrings outside the immediate change

---

## Exact change required

### 1. Add env var read at the top of `core/risk.py`, near the other gate constants

```python
MIN_ENTRY_PRICE = float(os.getenv("MIN_ENTRY_PRICE", "0.15"))
```

Place this near `MAX_ENTRY_PRICE` for readability.

### 2. Add the gate check inside `check_entry_gates()`, immediately after the `MAX_ENTRY_PRICE` check (lines ~186–189 in current source)

The existing block looks like:
```python
if sig.side == "BUY_YES" and ob.ask_yes is not None and ob.ask_yes >= MAX_ENTRY_PRICE:
    return False, [f"entry_price_too_high:{ob.ask_yes:.4f}>={MAX_ENTRY_PRICE:.4f}"]
if sig.side == "BUY_NO" and ob.ask_no is not None and ob.ask_no >= MAX_ENTRY_PRICE:
    return False, [f"entry_price_too_high:{ob.ask_no:.4f}>={MAX_ENTRY_PRICE:.4f}"]
```

Insert directly after those two lines:
```python
if MIN_ENTRY_PRICE > 0.0:
    if sig.side == "BUY_YES" and ob.ask_yes is not None and ob.ask_yes < MIN_ENTRY_PRICE:
        return False, [f"entry_price_too_low:{ob.ask_yes:.4f}<{MIN_ENTRY_PRICE:.4f}"]
    if sig.side == "BUY_NO" and ob.ask_no is not None and ob.ask_no < MIN_ENTRY_PRICE:
        return False, [f"entry_price_too_low:{ob.ask_no:.4f}<{MIN_ENTRY_PRICE:.4f}"]
```

### 3. Optionally add to .env (only if the worker judges it necessary for operator visibility)

```
MIN_ENTRY_PRICE=0.15
```

---

## Acceptance criteria

- [ ] `MIN_ENTRY_PRICE` constant added to `core/risk.py` near `MAX_ENTRY_PRICE`
- [ ] Gate check added in `check_entry_gates()` immediately after the `MAX_ENTRY_PRICE` check
- [ ] Gate applies to both BUY_YES (checks ask_yes) and BUY_NO (checks ask_no)
- [ ] Gate is skipped if `MIN_ENTRY_PRICE == 0.0` (allows disabling via env)
- [ ] Reason string format: `entry_price_too_low:{price}:{threshold}` — matches existing gate reason style
- [ ] `python -m py_compile core/risk.py` passes
- [ ] No other files modified except `.env` if the worker adds it there

---

## Required output

Write result to:
```
C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_MIN_ENTRY_PRICE_GATE_001.json
```

Structure:
```json
{
  "task_id": "MIN_ENTRY_PRICE_GATE_001",
  "status": "DONE",
  "read_only_confirmed": false,
  "files_modified": ["core/risk.py"],
  "files_read": [],
  "py_compile_pass": true,
  "constant_added": "MIN_ENTRY_PRICE = float(os.getenv(...))",
  "gate_inserted_after_line": 0,
  "env_updated": false,
  "reason_string_format": "entry_price_too_low:{price}:{threshold}",
  "change_summary": "",
  "rollback_instructions": "Remove the two if-blocks added to check_entry_gates() and remove the MIN_ENTRY_PRICE line near the top of risk.py"
}
```
