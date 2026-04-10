# Worker Handoff Note — SHADOW_001
## Created: 2026-04-04

---

## What this task is

Upgrade the MLB shadow panel in the sports_bot_v2 dashboard to show dollar-based PnL, entry/current prices, TP/SL target prices, and per-position status. Shadow mode stays advisory-only — no execution logic changes.

---

## Task brief location

`C:\Users\johnny\Desktop\BOT_BRIDGE\05_INBOX_FROM_MANAGER\TASK_SHADOW_001.json`

---

## The two files you may touch

```
C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html
C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py
```

Do not touch anything in `mlb_model`, execution logic, order placement, model training, or export/pipeline.

---

## Context you need to read first

Before writing any code, read these to understand the current data shape:

1. **Current shadow API payload** — run the dashboard server and hit:
   `http://localhost:8900/api/mlb-shadow`
   Note exactly which fields are present (entry price, current price, fair, edge, etc.)

2. **Shadow log format** — read recent entries from:
   `C:\Users\johnny\Desktop\mlb_model\logs\shadow_recommendations.jsonl`
   This is the source data the dashboard reads.

3. **Current dashboard shadow panel** — read `dashboard.html` and find the section rendering shadow positions. Note what is currently displayed vs. what needs to be added.

4. **dashboard_server.py** — find the `/api/mlb-shadow` endpoint and the `read_shadow_log()` function (or equivalent). This is where new fields need to be computed or passed through.

---

## What to build

For each shadow position, the dashboard must display:

| Field | Source | Notes |
|-------|--------|-------|
| Entry price | `market_yes_cost` or `market_no_cost` at signal time | Already in log |
| Current live price | Latest book price if available | May require passing through from API |
| Live unrealized PnL ($) | `(current_px - entry_px) * size_usd` for YES; inverted for NO | Compute in server or JS |
| TP target price | Derive from edge/fair: fair_win_prob (YES) or `1 - fair_win_prob` (NO) | Use as TP proxy |
| SL target price | Define a fixed SL band (e.g. entry - 0.10) or use existing stop logic if present | Keep simple |
| Status | OPEN, TP_ZONE, SL_ZONE, RESOLVED_WIN, RESOLVED_LOSS, PENDING | Derive from current price vs TP/SL |

Label the entire panel clearly: **"Shadow Advisory — Not Executed"** or equivalent.

---

## Sizing assumption

If no explicit shadow dollar size is in the log, use a fixed default (e.g. $50/position) for PnL calculation and label it as estimated. Do not invent execution logic — display only.

---

## How to verify

```
cd C:\Users\johnny\Desktop\sports_bot_v2
python dashboard_server.py
```

Open `http://localhost:8900` and confirm the MLB Shadow panel shows:
- Entry price per position
- Current price (or "N/A" if unavailable)
- Live unrealized PnL in dollars
- TP and SL target prices
- Status label (OPEN / TP_ZONE / SL_ZONE / RESOLVED_WIN / RESOLVED_LOSS / PENDING)
- "Advisory-only / not executed" label visible

---

## How to deliver

Write your result to:

```
C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_SHADOW_001.json
```

Use this structure:

```json
{
  "task_id": "SHADOW_001",
  "status": "done",
  "files_changed": ["dashboard.html", "dashboard_server.py"],
  "summary": ["..."],
  "commands_run": ["python dashboard_server.py"],
  "tests_run": ["Opened http://localhost:8900, confirmed shadow panel shows..."],
  "result": ["..."],
  "risks": ["..."],
  "next_recommended_task": "SHADOW_002 or none"
}
```

---

## Rollback

Revert `dashboard.html` and `dashboard_server.py` only. No other files were changed.
