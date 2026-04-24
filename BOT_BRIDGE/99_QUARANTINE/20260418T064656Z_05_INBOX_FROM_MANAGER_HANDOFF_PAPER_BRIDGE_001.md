# HANDOFF_PAPER_BRIDGE_001

## Status: ACTIVE

**Title**: Build guarded paper execution bridge from mlb_model recommendations to sports_bot_v2
**Priority**: MEDIUM
**Subsystem**: paper execution / model bridge
**Issued**: 2026-04-17
**Assigned**: HAIKU_WORKER

---

## What this task is

_(edit me — auto-generated stub)_

## Allowed files
- `C:\Users\johnny\Desktop\sports_bot_v2\core\model_bridge.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\bot_core.py`

## Acceptance

- model_bridge.py exists with all required gates implemented
- ENABLE_MODEL_BRIDGE = False is present at top of model_bridge.py and defaults to False in submitted patch
- get_approved_intents() returns empty list and logs BRIDGE DISABLED when ENABLE_MODEL_BRIDGE is False
- log deduplication: only latest entry per slug is evaluated, NO_TRADE entries are discarded before gating
- bot_core.py calls model_bridge and passes approved intents to paper_exec
- moneyline-only gate enforced — test that a spread recommendation is rejected
- same-day date gate enforced — test that a future-dated recommendation is rejected
- staleness gates enforced — rec age, game state age, book age all checked
- duplicate position gate enforced — second intent for same slug is rejected
- paper trade created when all gates pass — position appears in state.json or DB
- source label 'model_bridge' present on created position (exact string)
- no changes to paper_exec.py, risk.py, signal_base.py
- no real execution path exists — paper only

---

_Auto-generated stub. Replace with narrative brief; the dashboard will not overwrite this file once it exists._
