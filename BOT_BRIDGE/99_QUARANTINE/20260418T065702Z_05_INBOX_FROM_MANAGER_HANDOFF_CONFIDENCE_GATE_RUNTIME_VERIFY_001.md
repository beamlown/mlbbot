# HANDOFF_CONFIDENCE_GATE_RUNTIME_VERIFY_001

## Status: ACTIVE

**Title**: Verify runtime enforcement of MIN_ENTRY_CONFIDENCE=0.60 against post-restart live trades
**Priority**: HIGH
**Subsystem**: risk / entry-gating
**Issued**: 2026-04-10
**Assigned**: OPUS_AUDITOR

---

## What this task is

_(edit me — auto-generated stub)_

## Allowed files
- `trades_sports.db (SELECT only: trades WHERE id IN (223, 224))`
- `recent bot logs`
- `sports_bot_v2/bot_core.py`
- `sports_bot_v2/core/risk.py`
- `sports_bot_v2/.env`
- `sports_bot_v2/core/model_bridge.py (ONLY if explicitly needed — justify)`

## Forbidden files
- `dashboard.html`
- `dashboard_server.py`
- `core/paper_exec.py`
- `launch_all.py`
- `Any file not in allowed_files list`

## Acceptance

- read_only_confirmed: true
- No code modified, no DB writes, no restarts
- Restart time confirmed or corrected with log evidence
- Explicit BEFORE/AFTER verdict for trades 223 and 224
- Explicit YES/NO on whether bridge entries use check_entry_gates()
- Explicit YES/NO on whether 0.60 floor is loaded in live env/code
- Explicit conclusion on whether a real bug exists
- next_action field populated

---

_Auto-generated stub. Replace with narrative brief; the dashboard will not overwrite this file once it exists._
