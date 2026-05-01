# HANDOFF — RISK_001
## Confidence-tiered position sizing

---

## ✅ STATUS: ACTIVE — proceed immediately.

---

## Context

`core/paper_exec.py` line ~46 has:

```python
qty = PAPER_POSITION_SIZE_USD / fill_px
```

This always uses the fixed $50 base regardless of how confident the model is. The `signal.confidence` value (0.0–1.0) is already passed into `open_position()` and stored in the DB — we just never use it for sizing.

**Approach: tiered multiplier** (not Kelly criterion — Kelly requires accurate probability calibration that isn't validated yet; tiered scaling is transparent and easy to reason about).

**Do NOT touch**: `dashboard.html`, `dashboard_server.py`, `launch_all.py`, `bot_core.py`, `core/model_bridge.py`, `core/db.py`, `mlb_model/`

---

## Fix 1 — Add env vars to .env

Open `.env` and append after the `PAPER_POSITION_SIZE_USD` line:

```
# Confidence-based position sizing
CONF_SIZING_ENABLED=true
CONF_TIER_HIGH=0.70
CONF_TIER_VHIGH=0.80
CONF_SIZE_MID_MULT=1.25
CONF_SIZE_HIGH_MULT=1.50
MAX_POSITION_SIZE_USD=100
```

**Tier logic summary:**
- confidence < 0.70 → 1.0x ($50 base)
- confidence 0.70–0.79 → 1.25x ($62.50)
- confidence >= 0.80 → 1.50x ($75.00)
- Hard cap: $100 always

---

## Fix 2 — Add _confidence_size() and wire it into open_position()

**Step A** — At module level in `core/paper_exec.py`, after the existing `PAPER_POSITION_SIZE_USD` line, add:

```python
CONF_SIZING_ENABLED   = os.getenv("CONF_SIZING_ENABLED", "true").lower() == "true"
CONF_TIER_HIGH        = float(os.getenv("CONF_TIER_HIGH", "0.70"))
CONF_TIER_VHIGH       = float(os.getenv("CONF_TIER_VHIGH", "0.80"))
CONF_SIZE_MID_MULT    = float(os.getenv("CONF_SIZE_MID_MULT", "1.25"))
CONF_SIZE_HIGH_MULT   = float(os.getenv("CONF_SIZE_HIGH_MULT", "1.50"))
MAX_POSITION_SIZE_USD = float(os.getenv("MAX_POSITION_SIZE_USD", "100.0"))

def _confidence_size(base_usd: float, confidence: float) -> float:
    if not CONF_SIZING_ENABLED:
        return base_usd
    if confidence >= CONF_TIER_VHIGH:
        mult = CONF_SIZE_HIGH_MULT
    elif confidence >= CONF_TIER_HIGH:
        mult = CONF_SIZE_MID_MULT
    else:
        mult = 1.0
    return min(base_usd * mult, MAX_POSITION_SIZE_USD)
```

**Step B** — In `open_position()`, replace the single line:

```python
qty = PAPER_POSITION_SIZE_USD / fill_px
```

With:

```python
size_usd = _confidence_size(PAPER_POSITION_SIZE_USD, signal.confidence)
qty = size_usd / fill_px
```

`signal` is the parameter passed to `open_position()`. `signal.confidence` is already available — no other changes needed.

---

## Verification

After editing, trace the math manually:
- `confidence=0.65`, `base=50.0` → below CONF_TIER_HIGH → `mult=1.0` → `size_usd=50.0` → `qty=50.0/fill_px` ✓
- `confidence=0.72`, `base=50.0` → >= CONF_TIER_HIGH, < CONF_TIER_VHIGH → `mult=1.25` → `size_usd=62.5` → `qty=62.5/fill_px` ✓
- `confidence=0.82`, `base=50.0` → >= CONF_TIER_VHIGH → `mult=1.50` → `size_usd=75.0` → `qty=75.0/fill_px` ✓

Read back both files to confirm all changes are present before submitting RESULT.

---

## Rollback

Set `CONF_SIZING_ENABLED=false` in `.env` — all trades revert to $50 flat with no code changes. Or revert both `core/paper_exec.py` and `.env`.
