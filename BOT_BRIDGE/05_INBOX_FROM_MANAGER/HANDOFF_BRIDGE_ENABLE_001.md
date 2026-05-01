# HANDOFF — BRIDGE_ENABLE_001
## Re-enable model bridge kill switch

---

## Context

BRIDGE_FIX_001 (per-intent re-fetch + cap check) and LAUNCH_FIX_001B (ctypes PID guard) were both reviewed and APPROVED on 2026-04-04. The bridge re-enable gate is clear.

The kill switch is a single boolean at the top of `core/model_bridge.py`:

```python
ENABLE_MODEL_BRIDGE = False  # INCIDENT KILL SWITCH — set True only after dedup fix
```

---

## File to change

`sports_bot_v2/core/model_bridge.py` — line 11 ONLY.

---

## Exact change

**Before (line 11):**
```python
ENABLE_MODEL_BRIDGE = False  # INCIDENT KILL SWITCH — set True only after dedup fix
```

**After (line 11):**
```python
ENABLE_MODEL_BRIDGE = True
```

Remove the comment entirely. No other changes.

---

## Verification

```
cd C:\Users\johnny\Desktop\sports_bot_v2
python -c "from core.model_bridge import ENABLE_MODEL_BRIDGE; print(ENABLE_MODEL_BRIDGE)"
```

Must print: `True`

---

## Rollback

Revert `core/model_bridge.py` only. Change back to `ENABLE_MODEL_BRIDGE = False`.

**Do NOT restart the bot** — manager will handle that separately.
