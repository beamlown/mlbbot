# Worker Handoff Note — MLB_002
## Created: 2026-04-04

---

## What this task is

Fix two team abbreviation mismatches in `mlb_model/integration/recommendation_api.py` so that:
- `mlb-tor-cws-*` markets match ESPN registry team `CHW` (Chicago White Sox)
- `mlb-hou-oak-*` markets match ESPN registry team `ATH` (Oakland/Athletics)

Both games currently drop as `no_registry_match` and never reach the model.

---

## Task brief location

`C:\Users\johnny\Desktop\BOT_BRIDGE\05_INBOX_FROM_MANAGER\TASK_MLB_002.json`

---

## The one file you may touch

```
C:\Users\johnny\Desktop\mlb_model\integration\recommendation_api.py
```

Do not touch anything else.

---

## What to do

1. Open `recommendation_api.py` and find where team abbreviations from Kalshi slugs are compared to the ESPN registry.
2. Add alias mappings so that:
   - `cws` → `CHW`
   - `oak` → `ATH`
3. Make the smallest possible change — a lookup dict or an inline alias normalization step before the registry match.

---

## How to verify

From `C:\Users\johnny\Desktop\mlb_model\`:

```
python -m integration.recommendation_api
```

**Expected healthy output (when TOR@CWS or HOU@OAK games are live):**
- No `NOT-LIVE [no_registry_match]` for `mlb-tor-cws-*` or `mlb-hou-oak-*`
- These events appear as `candidate:` lines instead
- `duplicate_event_market` count remains 0

---

## How to deliver

Write your result to:

```
C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_MLB_002.json
```

Use this structure (from `03_TEMPLATES/RESULT_TEMPLATE.json`):

```json
{
  "task_id": "MLB_002",
  "status": "done",
  "files_changed": ["integration/recommendation_api.py"],
  "summary": ["..."],
  "commands_run": ["python -m integration.recommendation_api"],
  "tests_run": ["..."],
  "result": ["..."],
  "risks": ["..."],
  "next_recommended_task": "MLB_003"
}
```

---

## Rollback

Revert `recommendation_api.py` only. No other files were changed.
