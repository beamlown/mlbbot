# HANDOFF: CONFIG_HASH_INPUTS_FIX_001

## Status
QUEUED — do not activate until `LATE_INNING_BLOCK_WIRING_FIX_001` is APPROVED. Both tasks lock `bot_core.py` and `core/risk.py`.

## What you are doing
Expand the `config_hash` input variable list in `bot_core.py` so the hash reflects the real gate-critical variables. This is a one-location surgical change — no gate logic, no threshold changes, no strategy work.

## Why this exists
Tonight's config verification was misleading. `config_hash` did not change when `MIN_ENTRY_CONFIDENCE` or `MIN_ENTRY_PRICE` were updated in `.env` because those vars were never in the hash input set. The hash stayed at `2f0dd9e0ef8a` through multiple restarts and .env edits. This made it impossible to verify from state.json alone whether a restart had actually loaded new gate values.

## Why you must wait for LATE_INNING_BLOCK_WIRING_FIX_001
`LATE_INNING_BLOCK_WIRING_FIX_001` adds `LATE_INNING_BLOCK` as an active env var in `risk.py` or `bot_core.py`. If you run this task before that fix is approved, you would be adding `LATE_INNING_BLOCK` to the hash input list before the var is definitively in source. Wait for the fix to land, then include it.

## Why this must come before STARTUP_PROOF_BLOCK_001
`STARTUP_PROOF_BLOCK_001` will emit `config_hash` in the startup log. If this fix has not run first, the emitted hash is still derived from an incomplete input set. The proof block would exist but still mislead. Fix the inputs first — then make them observable.

## The change

Find this in `bot_core.py` (roughly the module-level CONFIG_HASH assignment):
```python
CONFIG_HASH = config_hash([
    "SPORT", "LOOP_SECONDS", "MAX_SPREAD", "MIN_DEPTH_TOP5_USD", "MIN_CONFIDENCE",
    "AUTO_TAKE_PROFIT_PCT", "AUTO_STOP_LOSS_PCT", "MAX_CONCURRENT_TRADES",
])
```

Expand it to include the missing gate-critical vars:
```python
# Gate-critical config vars — expand this list whenever a new threshold/block env var is added
CONFIG_HASH = config_hash([
    "AUTO_STOP_LOSS_PCT",
    "AUTO_TAKE_PROFIT_PCT",
    "LATE_INNING_BLOCK",
    "LOOP_SECONDS",
    "MAX_CONCURRENT_TRADES",
    "MAX_SPREAD",
    "MAX_TRADES_PER_MARKET",
    "MIN_CONFIDENCE",
    "MIN_DEPTH_TOP5_USD",
    "MIN_ENTRY_CONFIDENCE",
    "MIN_ENTRY_PRICE",
    "SPORT",
])
```
(Sorted alphabetically for determinism. Confirm exact var names match what `os.getenv()` reads in `risk.py`.)

## Conditional additions
If `SESSION_MARKET_TRADE_CAP_001` or `POST_GAP_STOP_SAME_SIDE_SESSION_BAN_001` have already landed and added new env vars (e.g. `MAX_SLUG_ENTRIES_SESSION`), include those too. If those tasks have not yet run, do not add phantom vars.

## What NOT to do
- Do not change any gate thresholds
- Do not modify `config_hash()` in `core/utils.py` (read it for context only)
- Do not touch `dashboard_server.py`, `launch_all.py`, or `mlb_model/`
- Do not add new gate logic

## Deliver back in result JSON
- `files_changed`
- `before_hash_inputs` — exact prior list
- `after_hash_inputs` — exact new list
- `conditional_vars_found` — session-level anti-repeat vars found in source (if any)
- `py_compile_results` — PASS/FAIL per file
- `restart_required`
