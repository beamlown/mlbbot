# Worker Handoff Note — PAPER_BRIDGE_003
## Created: 2026-04-04

---

## PAPER MODE ONLY

No real money. No live order placement. Paper trades to local SQLite DB only.

---

## What this task is

This is the live verification pass for the model bridge built in PAPER_BRIDGE_002. The entire code change is one line:

```python
# core/model_bridge.py — line 1
ENABLE_MODEL_BRIDGE = True   # was False
```

That's it. Nothing else changes.

---

## Task brief location

`C:\Users\johnny\Desktop\BOT_BRIDGE\05_INBOX_FROM_MANAGER\TASK_PAPER_BRIDGE_003.json`

---

## The one file you may touch

```
C:\Users\johnny\Desktop\sports_bot_v2\core\model_bridge.py
```

Change `ENABLE_MODEL_BRIDGE = False` to `ENABLE_MODEL_BRIDGE = True`. Do not touch any other file.

---

## What you are verifying

| What to check | What healthy looks like |
|---------------|------------------------|
| Kill switch is off | No `BRIDGE DISABLED` lines in logs |
| Gate rejections working | `BRIDGE GATE REJECT [gate_name] slug=...` lines appearing each loop |
| No crashes | Bot completes loops cleanly, existing paper trade logic unaffected |
| Gate pass (if conditions met) | `BRIDGE GATE PASS slug=... side=... edge=... confidence=...` |
| Source label (if gate pass) | `runtime/state.json` open position has `source=model_bridge` |

---

## What rejection reasons are normal

Most loops will produce rejections. These are all correct behavior — not failures:

- `rec_too_stale` — recommendation is older than 120s (common if shadow engine isn't running fresh)
- `slug_date_mismatch` — slug dated tomorrow, not today
- `not_live` — game hasn't started yet
- `confidence_too_low` — model confidence below 0.25
- `edge_too_small` — edge below 0.05
- `slug_already_open` — position already exists for this game
- `no_actionable_recs` — all entries were NO_TRADE or log is empty

If only rejections appear during the window and no GATE PASS occurs — that is acceptable. Report the rejection reasons and confirm no crashes.

---

## How to run

```
cd C:\Users\johnny\Desktop\sports_bot_v2
python bot_core.py
```

Let it run for at least 2-3 full loops (~90 seconds minimum). Watch the logs.

---

## How to deliver

Write your result to:

```
C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_PAPER_BRIDGE_003.json
```

Include:
- `files_changed`: `["core/model_bridge.py"]` only
- `kill_switch_status`: `"ENABLE_MODEL_BRIDGE = True — confirmed active"`
- `gate_reject_lines`: paste the exact BRIDGE GATE REJECT lines you saw
- `gate_pass_lines`: paste any BRIDGE GATE PASS lines, or `"none observed in this window"`
- `model_bridge_position`: paste the state.json entry if created, or `"none — no gate pass in this window"`
- `existing_trades_unaffected`: confirm yes/no
- `risks`: any issues observed
- `next_recommended_task`

---

## Rollback

Set `ENABLE_MODEL_BRIDGE = False` in `core/model_bridge.py`. That's the complete rollback.
