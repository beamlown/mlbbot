# HANDOFF_RESTART_CONFIG_HASH_VERIFY_001

## Status: ACTIVE

**Title**: Verify clean restart loaded new .env config — confirm gates enforcing at new thresholds
**Priority**: CRITICAL
**Subsystem**: runtime / entry gates / process topology
**Issued**: 2026-04-10
**Assigned**: OPUS_AUDITOR

---

## What this task is

_(edit me — auto-generated stub)_

## Allowed files
- `C:\Users\johnny\Desktop\sports_bot_v2\runtime\state.json`
- `C:\Users\johnny\Desktop\sports_bot_v2\logs\bot_baseball_20260411.log`
- `C:\Users\johnny\Desktop\sports_bot_v2\logs\bot_baseball_20260412.log`

## Forbidden files
- `C:\Users\johnny\Desktop\sports_bot_v2\bot_core.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\core\risk.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\.env`
- `Any file not listed above`

## Acceptance

- config_hash in state.json is different from '2f0dd9e0ef8a'
- Bot log startup line shows min_conf=0.65 (or shows the correct loaded threshold)
- At least one BRIDGE GATE REJECT log entry confirms confidence threshold is 0.65
- No trade opened post-restart with confidence < 0.65
- No trade opened post-restart with entry_px < 0.22
- Exactly one bot_core process running
- session_start_ts is fresh (within 5 minutes of relaunch)

---

_Auto-generated stub. Replace with narrative brief; the dashboard will not overwrite this file once it exists._
