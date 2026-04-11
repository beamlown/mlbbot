# HANDOFF — BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001
**Priority:** HIGH
**Type:** Code fix — bridge loop dedup
**Issued:** 2026-04-11
**Status:** QUEUED — execute before MARKET_COOLDOWN_PERSIST_001 (both touch bot_core.py; this task first)
**Scope:** NARROW — bridge loop in `bot_core.py` only. Add a per-iteration rejected-slug set. Do not touch model_bridge.py or check_entry_gates().

---

## One-sentence task

Add a per-bridge-loop rejected-slug set so that if `check_entry_gates()` rejects an intent for a given slug, any subsequent intent for that same slug in the same loop iteration is also blocked.

---

## Why this exists

CONFIDENCE_GATE_POSTFIX_VERIFY_001 (PARTIAL PASS, 2026-04-10) confirmed Issue A:

**What happened with trade #236:**
1. `get_approved_intents()` returned TWO intents for slug `mlb-mia-det-2026-04-10` in the same bridge loop
2. First intent: `check_entry_gates()` correctly rejected (confidence_too_low:0.56:0.600)
3. Second intent: the rejected slug was NOT tracked — no dedup existed
4. Second intent bypassed because slug was not in `current_open_slugs` (no trade was opened for it yet)
5. For an unknown reason, `check_entry_gates()` did not reject the second call — trade #236 opened at conf=0.56

The fix must be: track rejected slugs within the loop iteration and block any subsequent intent for the same slug immediately, without a second gate call.

---

## What you must NOT do

- Touch `core/model_bridge.py` (dedup in model_bridge is a separate investigation)
- Touch `check_entry_gates()` in `core/risk.py`
- Refactor the broader bridge loop
- Add logging beyond a single info line for the dedup block
- Touch dashboard files, .env, or any other file

---

## Where to look

Find the bridge entry loop in `bot_core.py`. It currently looks like:

```python
bridge_intents = get_approved_intents(open_slugs)
for intent in bridge_intents:
    current_open = fetch_open_trades()
    if len(current_open) >= MAX_CONCURRENT_TRADES:
        ...
        break
    ...
    _gate_ok, _gate_reasons = check_entry_gates(...)
    if not _gate_ok:
        logger.info("BRIDGE GATE REJECT [check_entry_gates] slug=%s reasons=%s", ...)
        ...
        continue
    ...
    open_position(...)
```

---

## What to add

Before the loop, initialize a rejected-slug set:
```python
_loop_rejected_slugs: set[str] = set()
```

Inside the loop, immediately before calling `check_entry_gates()`, add:
```python
if market.slug in _loop_rejected_slugs:
    logger.info(
        "BRIDGE GATE REJECT [dupe_slug] slug=%s already rejected this loop",
        market.slug,
    )
    _guard_block_count += 1
    loop_guard_reasons.append(f"bridge:dupe_slug_rejected")
    continue
```

After the existing `if not _gate_ok:` block, add the slug to the rejected set:
```python
_loop_rejected_slugs.add(market.slug)
```

---

## Acceptance criteria

- [ ] `_loop_rejected_slugs` set initialized before the `for intent in bridge_intents:` loop
- [ ] Check for `market.slug in _loop_rejected_slugs` runs before `check_entry_gates()`
- [ ] On rejection by `check_entry_gates()`, slug is added to `_loop_rejected_slugs`
- [ ] Log line for dupe-slug block: `BRIDGE GATE REJECT [dupe_slug] slug=... already rejected this loop`
- [ ] `python -m py_compile bot_core.py` passes
- [ ] No other files modified

---

## Required output

Write result to:
```
C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001.json
```

Structure:
```json
{
  "task_id": "BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001",
  "status": "DONE",
  "read_only_confirmed": false,
  "files_modified": ["bot_core.py"],
  "py_compile_pass": true,
  "set_initialized_line": 0,
  "dedup_check_line": 0,
  "slug_add_on_reject_line": 0,
  "log_format": "BRIDGE GATE REJECT [dupe_slug] slug=... already rejected this loop",
  "change_summary": "",
  "rollback_instructions": "Remove _loop_rejected_slugs initialization, the dedup check block, and the _loop_rejected_slugs.add() call"
}
```
