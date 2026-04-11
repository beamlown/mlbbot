# HANDOFF — TP_NEAR_RESOLUTION_CAP_FIX_001
**Priority:** HIGH
**Type:** Code fix — narrow math correction
**Issued:** 2026-04-11
**Scope:** NARROW — `get_tp_price()` in `core/risk.py` only, plus optionally a near-resolution entry gate addition. Do not touch SL logic, gap_stop logic, or other exit conditions.

---

## One-sentence task

Fix the TP price formula so it cannot exceed 1.0 on binary (0–1) Polymarket contracts, which currently causes take-profit to become unreachable for positions entered at high prices (e.g., 0.94+).

---

## Why this exists

Tonight's audit found trade #259: BUY_NO nyy-tb, `entry_px = 0.9447`.

```
get_tp_price = 0.9447 × 1.40 = 1.3226   ← UNREACHABLE (contract max = 1.0)
```

The TP condition (`current_held_price >= tp_price`) will never fire. The position can only exit via SL, gap_stop, trailing_stop, near_resolution, or time_exit. This makes the near-resolution position asymmetrically loss-exposed: max gain ≈ $2.93 vs max loss ≈ $5.99 + fees.

This is a structural math bug. Any entry above approximately 0.714 produces a TP above 1.0.

---

## What you must NOT do

- Touch `check_exit()` logic beyond what is strictly necessary
- Change the SL formula (`get_sl_price`)
- Touch gap_stop threshold
- Touch trailing_stop logic
- Modify `bot_core.py`, `dashboard_server.py`, or any file other than `core/risk.py`
- Add tests, docstrings, or comments beyond the immediate change
- Widen scope to refactor the entire exit logic

---

## Preferred fix

### Option A (preferred) — Cap TP in `get_tp_price()`

Modify `get_tp_price()` in `core/risk.py`:

**Current:**
```python
def get_tp_price(trade: Trade) -> float:
    entry_px = trade.entry_px or 0.0
    return entry_px * (1.0 + AUTO_TAKE_PROFIT_PCT)
```

**Change to:**
```python
def get_tp_price(trade: Trade) -> float:
    entry_px = trade.entry_px or 0.0
    raw_tp = entry_px * (1.0 + AUTO_TAKE_PROFIT_PCT)
    return min(raw_tp, NEAR_RESOLUTION_PRICE)
```

This caps the TP at `NEAR_RESOLUTION_PRICE` (already defined in `risk.py`). If entry is so high that TP would exceed 1.0, the position effectively targets the near_resolution exit instead.

### Option B (fallback if Option A creates any edge case)

Add a minimum price check at entry for both sides that blocks entries where `entry_px > (NEAR_RESOLUTION_PRICE / (1.0 + AUTO_TAKE_PROFIT_PCT))`. This is approximately `entry_px > 0.693` for TP=40%, NEAR_RES=0.97.

If the worker judges Option B to be safer for the codebase, use it. Justify explicitly in the result.

---

## Read first before editing

Read `core/risk.py` lines 1–80 to confirm:
- Where `NEAR_RESOLUTION_PRICE` is defined
- Where `AUTO_TAKE_PROFIT_PCT` is defined
- Where `get_tp_price()` is defined
- Exact current line numbers

---

## Acceptance criteria

- [ ] `get_tp_price()` can no longer return a value above `NEAR_RESOLUTION_PRICE`
- [ ] For entry_px = 0.9447, TP price is now `NEAR_RESOLUTION_PRICE` (e.g., 0.97 or whatever is defined), not 1.32
- [ ] For entry_px = 0.37 (normal entry), TP price is unchanged (0.37 × 1.40 = 0.518 < 0.97, no effect)
- [ ] `python -m py_compile core/risk.py` passes
- [ ] No other files modified

---

## Required output

Write result to:
```
C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_TP_NEAR_RESOLUTION_CAP_FIX_001.json
```

Structure:
```json
{
  "task_id": "TP_NEAR_RESOLUTION_CAP_FIX_001",
  "status": "DONE",
  "read_only_confirmed": false,
  "option_used": "A or B",
  "files_modified": ["core/risk.py"],
  "py_compile_pass": true,
  "near_resolution_price_value": 0.0,
  "tp_formula_before": "entry_px * (1.0 + AUTO_TAKE_PROFIT_PCT)",
  "tp_formula_after": "",
  "example_entry_0947_tp_before": 1.3226,
  "example_entry_0947_tp_after": 0.0,
  "example_entry_037_tp_unchanged": true,
  "change_summary": "",
  "rollback_instructions": "Revert get_tp_price() to original single-line return"
}
```
