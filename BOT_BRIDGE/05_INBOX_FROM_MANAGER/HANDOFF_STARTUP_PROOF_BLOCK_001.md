# HANDOFF: STARTUP_PROOF_BLOCK_001

## Status
QUEUED — do not activate until `CONFIG_HASH_INPUTS_FIX_001` is APPROVED. All three consecutive tasks (`LATE_INNING_BLOCK_WIRING_FIX_001` → `CONFIG_HASH_INPUTS_FIX_001` → this one) lock `bot_core.py` and/or `core/risk.py`. They run in series, not parallel.

## What you are doing
Add one structured startup proof block to `bot_core.py` that makes runtime identity and loaded config verifiable from the log. This is a single log emission added to the startup flow. No logic changes, no threshold changes, no dashboard work.

## Why this exists
Tonight proved that restart claims are not independently verifiable. The process restarted multiple times, but:
- `config_hash` stayed at `2f0dd9e0ef8a` through every restart
- The startup banner showed `min_conf=0.25` which is `MIN_CONFIDENCE` (the pre-filter), not `MIN_ENTRY_CONFIDENCE` (the hard floor) — these are different vars
- Two processes ran simultaneously with no way to tell from a log line which one was authoritative
- There was no single grep-able line proving "this process started, loaded these values, and is authoritative"

## Why this must come after CONFIG_HASH_INPUTS_FIX_001
This proof block will emit `config_hash`. If `CONFIG_HASH_INPUTS_FIX_001` has not run first, the emitted hash is still derived from the incomplete input set (`MIN_ENTRY_CONFIDENCE` and `MIN_ENTRY_PRICE` still absent). The proof block would exist but the hash field inside it would still mislead.

**Fix the inputs, then make them observable. Never the other way.**

## What to add

In `bot_core.py`, find the startup initialization block (after `load_env()` and after the module-level constants are set, before the main loop). Add exactly one proof emission:

```python
# Startup proof — emit once per process start for log-based restart verification
logger.info(
    "STARTUP_PROOF %s",
    json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "python": sys.executable,
        "cwd": os.getcwd(),
        "env_path": str(_ENV_PATH),
        "config_hash": CONFIG_HASH,
        "gates": {
            "MIN_ENTRY_CONFIDENCE": float(os.getenv("MIN_ENTRY_CONFIDENCE", "0.60")),
            "MIN_ENTRY_PRICE": float(os.getenv("MIN_ENTRY_PRICE", "0.15")),
            "MIN_CONFIDENCE": float(os.getenv("MIN_CONFIDENCE", "0.25")),
            "MAX_CONCURRENT_TRADES": int(os.getenv("MAX_CONCURRENT_TRADES", "3")),
            "MAX_TRADES_PER_MARKET": int(os.getenv("MAX_TRADES_PER_MARKET", "1")),
            "LATE_INNING_BLOCK": int(os.getenv("LATE_INNING_BLOCK", "0")),
            "AUTO_STOP_LOSS_PCT": float(os.getenv("AUTO_STOP_LOSS_PCT", "0.20")),
            "LOOP_SECONDS": int(os.getenv("LOOP_SECONDS", "30")),
        },
    }, separators=(",", ":")),
)
```

**Key rules:**
- Use the same `os.getenv()` defaults that `risk.py` uses — do not hardcode different defaults
- Use `CONFIG_HASH` directly — the constant already computed from the corrected input list. Do not recompute it.
- `_ENV_PATH` should already be defined in bot_core.py — use it
- `json`, `sys`, `os`, `datetime`, `timezone` — check which are already imported in bot_core.py and add only what is missing

## What the log line looks like
```
2026-04-11 10:32:17,042 [INFO] bot_core: STARTUP_PROOF {"ts":"2026-04-11T15:32:17.042Z","pid":12345,"python":"C:/Python313/python.exe","cwd":"C:/Users/johnny/Desktop/sports_bot_v2","env_path":"C:/Users/johnny/Desktop/sports_bot_v2/.env","config_hash":"a3f9c2b1d7e4","gates":{"MIN_ENTRY_CONFIDENCE":0.65,"MIN_ENTRY_PRICE":0.22,"MIN_CONFIDENCE":0.25,"MAX_CONCURRENT_TRADES":3,"MAX_TRADES_PER_MARKET":1,"LATE_INNING_BLOCK":7,"AUTO_STOP_LOSS_PCT":0.2,"LOOP_SECONDS":30}}
```

After restart, the operator can grep `STARTUP_PROOF` and see everything in one line.

## What NOT to do
- Do not fork a second `config_hash()` call with different inputs — use the existing `CONFIG_HASH` constant
- Do not add a second proof block — exactly one per process start
- Do not change any gate logic or thresholds
- Do not touch `launch_all.py`, `dashboard_server.py`, or `mlb_model/`
- Do not add a version counter or restart counter that modifies state.json

## Deliver back in result JSON
- `files_changed`
- `proof_block_location` — line number and context in bot_core.py
- `proof_block_format` — exact log line example
- `imports_added` — any new imports added
- `config_hash_source` — confirm it is the existing CONFIG_HASH constant, not a re-derived value
- `py_compile_results` — PASS/FAIL per file
- `restart_required`
