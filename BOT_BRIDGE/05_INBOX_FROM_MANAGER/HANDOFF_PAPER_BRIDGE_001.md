# Worker Handoff Note — PAPER_BRIDGE_001
## Created: 2026-04-04

---

## PAPER MODE ONLY

This task creates paper trades only. No real money. No live order placement. No connection to any exchange, broker, or betting platform. The bridge reads a local log file and writes to a local SQLite paper trade database only.

---

## What this task is

Build a guarded bridge between two existing systems:

- **Source:** `mlb_model` shadow recommendations (read from a local log file — no mlb_model code imported)
- **Destination:** `sports_bot_v2` paper execution (call existing paper_exec machinery — do not rewrite it)

The bridge is a gating layer. Its only job is to read recommendations, reject anything that fails a safety check, and pass approved intents to paper execution.

---

## Task brief location

`C:\Users\johnny\Desktop\BOT_BRIDGE\05_INBOX_FROM_MANAGER\TASK_PAPER_BRIDGE_001.json`

---

## The two files you may touch

```
C:\Users\johnny\Desktop\sports_bot_v2\core\model_bridge.py   ← NEW file you create
C:\Users\johnny\Desktop\sports_bot_v2\bot_core.py             ← minimal addition only
```

**Do not touch anything else.** Specifically:
- `paper_exec.py` — read it, call it, do not modify it
- `risk.py`, `signal_base.py` — do not touch
- `dashboard.html`, `dashboard_server.py` — do not touch
- Anything in `mlb_model/` — read the log file only, no code imports

---

## Read these first before writing anything

```
C:\Users\johnny\Desktop\mlb_model\logs\shadow_recommendations.jsonl
```
Understand the field names: `model_version`, `action`, `market_yes_cost`, `market_no_cost`, `edge_yes`, `edge_no`, `confidence`, `game_state_age_sec`, `book_age_sec`, `market_slug`, `feature_timestamp`, `is_home_team`, `tracked_team`.

```
C:\Users\johnny\Desktop\sports_bot_v2\core\paper_exec.py
```
Understand how to open a paper position. What arguments does it expect? What does it return?

```
C:\Users\johnny\Desktop\sports_bot_v2\core\db.py
```
Understand how to query existing open positions for a given slug.

```
C:\Users\johnny\Desktop\sports_bot_v2\bot_core.py
```
Find where to insert the bridge call — after the existing discovery/signal loop, not replacing it.

---

## What to build

### 1. `core/model_bridge.py` — new file

Put all constants at the top:

```python
ENABLE_MODEL_BRIDGE = False   # kill switch — default False, user flips manually after verification

APPROVED_MODEL_VERSIONS = {"mlb_winprob_v1_lgbm"}
MAX_REC_AGE_SECONDS = 120
MIN_EDGE = 0.05
MIN_CONFIDENCE = 0.25
MAX_GAME_STATE_AGE = 60
MAX_BOOK_AGE = 30
SHADOW_LOG_PATH = "../mlb_model/logs/shadow_recommendations.jsonl"
SOURCE_LABEL = "model_bridge"   # exact string used on all created paper positions
```

Main function signature (suggestion):

```python
def get_approved_intents(open_slugs: set[str]) -> list[dict]:
    """
    Read shadow log, apply all gates, return list of approved paper trade intents.
    open_slugs: set of event slugs already holding an open paper position.
    Returns: list of dicts with keys: slug, side, entry_px, source
    """
```

**Step 0 — Kill switch (check this before anything else):**

```python
ENABLE_MODEL_BRIDGE = False   # ← must stay False in submitted patch

if not ENABLE_MODEL_BRIDGE:
    logger.info("BRIDGE DISABLED — set ENABLE_MODEL_BRIDGE=True to activate")
    return []
```

Do not set this to True in your patch. The user will flip it manually after review.

**Step 1 — Deduplicate the log before any gate runs:**

The shadow log accumulates entries across many loops. The same slug may appear dozens of times. Before evaluating any gate:

1. Read the full log (or last N lines for efficiency)
2. Discard all entries where `action == "NO_TRADE"` — these are never execution candidates
3. For the remaining entries, keep only the **latest entry per `market_slug`** (use `feature_timestamp` or `ts` field to determine recency)
4. Your working set is now at most one entry per slug

This deduplication must happen before gates are evaluated, not after.

**Step 2 — Gates to implement in order (stop at first failure, log the rejection reason):**

1. `model_version` in `APPROVED_MODEL_VERSIONS`
2. `action` is `BUY_YES` or `BUY_NO` — not `NO_TRADE` or anything else
3. Recommendation age: `now - feature_timestamp < MAX_REC_AGE_SECONDS`
4. Market type: slug must NOT contain `nrfi`, `spread`, `total`, `o/u`, `props` — moneyline only
5. Slug date matches today's date (extract date from slug, compare to `date.today()`)
6. Edge exceeds threshold: `edge_yes >= MIN_EDGE` (for BUY_YES) or `edge_no >= MIN_EDGE` (for BUY_NO)
7. `confidence >= MIN_CONFIDENCE`
8. `game_state_age_sec < MAX_GAME_STATE_AGE`
9. `book_age_sec < MAX_BOOK_AGE`
10. Slug not already in `open_slugs` (no duplicate position for same game)
11. Deduplicate within the same batch: only one intent per slug

Log each rejection: `BRIDGE GATE REJECT [gate_name] slug=... reason=...`
Log each pass: `BRIDGE GATE PASS slug=... side=... edge=... confidence=...`

### 2. `bot_core.py` — minimal addition

After the existing main loop body, add:

```python
# Model bridge — paper trades from approved recommendations
from core.model_bridge import get_approved_intents
open_slugs = {pos["market_slug"] for pos in current_open_positions}
intents = get_approved_intents(open_slugs)
for intent in intents:
    # call existing paper_exec with source tag
    paper_exec.open_position(..., source="model_bridge")
```

Find the right insertion point by reading bot_core.py first. Do not replace existing logic — add only.

---

## How to verify

```
cd C:\Users\johnny\Desktop\sports_bot_v2
python bot_core.py
```

Check logs for:
- `BRIDGE GATE REJECT` entries with reason (proves gating is working)
- `BRIDGE GATE PASS` entries (proves a recommendation was approved)
- New entry in `runtime/state.json` open positions with `source=model-driven paper trade` (if a live game is available)

Also confirm:
- `paper_exec.py` is unchanged
- `risk.py` is unchanged
- `signal_base.py` is unchanged

---

## How to deliver

Write your result to:

```
C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_PAPER_BRIDGE_001.json
```

Include:
- `files_changed`: list the exact files modified
- `summary`: describe the bridge logic built
- `gates_implemented`: list all 11 gates and their threshold values
- `commands_run`
- `tests_run`: describe what gate passes and rejections you observed
- `result`: what you saw in logs / state.json
- `risks`: any residual risks
- `next_recommended_task`

---

## Rollback

Delete `core/model_bridge.py` and revert `bot_core.py`. No other files were modified.
