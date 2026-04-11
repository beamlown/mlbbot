# HANDOFF — MARKET_COOLDOWN_PERSIST_001
**Priority:** HIGH
**Type:** Code fix — state persistence
**Issued:** 2026-04-11
**Status:** QUEUED — do not execute until BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001 is DONE (both touch bot_core.py; execute sequentially)
**Scope:** NARROW — bot_core.py cooldown persist/reload path only. Do not refactor the full state write system.

---

## One-sentence task

Persist the `_market_cooldown` dict (market_id → expiry timestamp) into `runtime/state.json` on every state write, and reload it on startup, so market cooldowns survive process restarts.

---

## Why this exists

Tonight's audit found that after a restart at 00:50:22 UTC, the bot immediately re-entered CWS-KC (market_id 1860423) which had just produced a gap_stop close with a 3600s cooldown — because `_market_cooldown` is an in-memory-only dict, wiped on every restart.

**Timeline evidence:**
- #246 closed 01:01:08 with gap_stop → cooldown set to 02:01:08 UTC
- Restart at 00:50:22 wiped the dict
- #247 opened 01:02:41 — only 93 seconds after #246 closed, cooldown bypassed

Additionally: even without restarts, if `check_entry_gates()` is not being called (the pyc bug), the cooldown is written but never read. Persistence does not fix that — it only ensures survival across restarts once the gate is functional.

---

## What you must NOT do

- Refactor the full `_write_state()` system
- Change cooldown durations or SL/gap_stop close logic
- Touch `core/risk.py` (ACTIVE conflict with MIN_ENTRY_PRICE_GATE_001 or TP fix)
- Touch `dashboard_server.py` or `dashboard.html`
- Widen scope to rewrite the state module

---

## What to change

### Step 1 — Read current `_write_state()` in `bot_core.py`

Find the `_write_state()` function. It writes a JSON file to `runtime/state.json`. Add a `market_cooldowns` field to the output dict:

```python
"market_cooldowns": {
    mid: expiry
    for mid, expiry in _market_cooldown.items()
    if expiry > time.time()   # only persist active (not expired) cooldowns
}
```

### Step 2 — Read startup / `main()` in `bot_core.py`

Find the startup initialization section. After `_market_cooldown: dict[str, float] = {}` is initialized, add a reload block:

```python
_state_path = os.path.join(RUNTIME_DIR, "state.json")
if os.path.exists(_state_path):
    try:
        with open(_state_path) as _f:
            _saved = json.load(_f)
        _now = time.time()
        for _mid, _exp in _saved.get("market_cooldowns", {}).items():
            if float(_exp) > _now:
                _market_cooldown[_mid] = float(_exp)
        if _market_cooldown:
            logger.info(
                "Reloaded %d active market cooldowns from state.json",
                len(_market_cooldown),
            )
    except Exception as _e:
        logger.warning("Could not reload market_cooldowns from state.json: %s", _e)
```

---

## Acceptance criteria

- [ ] `_write_state()` writes `market_cooldowns` dict (active only, not expired entries) to `runtime/state.json`
- [ ] On startup, `bot_core.py` reads `market_cooldowns` from `state.json` and restores only entries whose expiry is in the future
- [ ] If `state.json` does not exist or is malformed, startup proceeds normally with empty cooldown dict
- [ ] `python -m py_compile bot_core.py` passes
- [ ] No other files modified

---

## Required output

Write result to:
```
C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_MARKET_COOLDOWN_PERSIST_001.json
```

Structure:
```json
{
  "task_id": "MARKET_COOLDOWN_PERSIST_001",
  "status": "DONE",
  "read_only_confirmed": false,
  "files_modified": ["bot_core.py"],
  "py_compile_pass": true,
  "write_state_field_added": "market_cooldowns",
  "startup_reload_added": true,
  "expired_entries_filtered": true,
  "state_missing_graceful": true,
  "change_summary": "",
  "rollback_instructions": "Remove market_cooldowns from _write_state() output dict; remove the reload block from main() startup"
}
```
