# REVIEW_RISK_001

Decision: APPROVED

## What passed

- **Scope**: only `core/paper_exec.py` and `.env` modified — matches allowed_files exactly. ✅
- **Env vars in .env** (lines 33-38): All 6 vars present with correct values:
  `CONF_SIZING_ENABLED=true`, `CONF_TIER_HIGH=0.70`, `CONF_TIER_VHIGH=0.80`,
  `CONF_SIZE_MID_MULT=1.25`, `CONF_SIZE_HIGH_MULT=1.50`, `MAX_POSITION_SIZE_USD=100`. ✅
- **Module-level env reads** (lines 18-23): All 6 vars read with correct defaults. Worker used a stricter boolean parse (`in {"1", "true", "yes", "on"}`) — more robust than the spec's `.lower() == "true"`. ✅
- **_confidence_size() function** (lines 26-39): Tier logic matches spec exactly. Worker added a `base_usd <= 0` guard that returns 0.0 — safe defensive check. Hard cap via `min(sized, MAX_POSITION_SIZE_USD)` applied. ✅
- **open_position() wired** (lines 68-69):
  ```python
  size_usd = _confidence_size(PAPER_POSITION_SIZE_USD, signal.confidence)
  qty = size_usd / fill_px if fill_px > 0 else 0.0
  ```
  Worker also added `fill_px > 0` guard on qty — prevents divide-by-zero. ✅
- **Tier math verified**:
  - confidence=0.65 → mult=1.0 → size=$50.00 ✓
  - confidence=0.72 → mult=1.25 → size=$62.50 ✓
  - confidence=0.82 → mult=1.50 → size=$75.00 ✓
- **Kill switch**: `CONF_SIZING_ENABLED=false` in .env → reverts to flat $50. ✅
- **Rollback**: revert `core/paper_exec.py` + `.env`, or toggle env var. ✅

## What failed

- None.

## Next action

All three Round 1 tasks approved. Promote DASH_016 to ACTIVE. After DASH_016 approved, relaunch bots.
