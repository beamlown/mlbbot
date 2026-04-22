# HANDOFF — DASH_005
## Add bridge_enabled field to /api/state

---

## Context

The dashboard needs to show a bridge health badge (BRIDGE ON / BRIDGE OFF) in the header. The `/api/state` endpoint is the data source for all header/HUD fields. Currently it does not include the bridge kill switch status.

The kill switch lives at `core/model_bridge.py` line 11 as `ENABLE_MODEL_BRIDGE: bool`.

---

## File to change

`sports_bot_v2/dashboard_server.py` — ONLY this file.

---

## Change

### Option A — top-level import (preferred if no circular import risk)

**At the top of dashboard_server.py, after existing imports, add:**
```python
try:
    from core.model_bridge import ENABLE_MODEL_BRIDGE as _BRIDGE_ENABLED
except Exception:
    _BRIDGE_ENABLED = False
```

**In `_read_state()` (around line 293, before the `return state` line), add:**
```python
        state["bridge_enabled"] = _BRIDGE_ENABLED
```

---

### Option B — inline import (if Option A causes an import error)

**In `_read_state()`, replace:**
```python
        state["stale"] = age > BOT_STALE_SEC
        state["file_age_sec"] = round(age, 1)
        return state
```

**With:**
```python
        state["stale"] = age > BOT_STALE_SEC
        state["file_age_sec"] = round(age, 1)
        try:
            from core.model_bridge import ENABLE_MODEL_BRIDGE
            state["bridge_enabled"] = ENABLE_MODEL_BRIDGE
        except Exception:
            state["bridge_enabled"] = False
        return state
```

Use whichever option works without import errors. Prefer Option A.

---

## Verification

```
cd C:\Users\johnny\Desktop\sports_bot_v2
python dashboard_server.py
```

In a second terminal:
```
curl http://localhost:5000/api/state
```

The JSON response must contain `"bridge_enabled": true` (or false if the kill switch is off).

## Rollback

Revert `dashboard_server.py` only.
