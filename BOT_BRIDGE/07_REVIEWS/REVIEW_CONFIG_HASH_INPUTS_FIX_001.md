# REVIEW_CONFIG_HASH_INPUTS_FIX_001.md

## Verdict
APPROVED

## Decision
Approve `CONFIG_HASH_INPUTS_FIX_001`. Move to DONE. Activate `STARTUP_PROOF_BLOCK_001` as next.

## What was confirmed

- Worker stayed within allowed scope — only `bot_core.py` modified.
- Single-location change: the active `config_hash([...])` call was found and expanded. No other logic touched.
- All prior vars retained — no accidental removals.
- Four required gate vars added: `MIN_ENTRY_CONFIDENCE`, `MIN_ENTRY_PRICE`, `MAX_TRADES_PER_MARKET`, `LATE_INNING_BLOCK`.
- Three session-level risk vars found in source and correctly included: `SESSION_MAX_LOSS_USD`, `DAILY_MAX_LOSS_USD`, `MAX_TOTAL_COMMITTED_USD`. All three back completed approved tasks (SESSION_LOSS_CAP_001, SESSION_EXPOSURE_CAP_001) — inclusion is correct.
- Final sorted list (15 vars): `AUTO_STOP_LOSS_PCT`, `AUTO_TAKE_PROFIT_PCT`, `DAILY_MAX_LOSS_USD`, `LATE_INNING_BLOCK`, `LOOP_SECONDS`, `MAX_CONCURRENT_TRADES`, `MAX_SPREAD`, `MAX_TOTAL_COMMITTED_USD`, `MAX_TRADES_PER_MARKET`, `MIN_CONFIDENCE`, `MIN_DEPTH_TOP5_USD`, `MIN_ENTRY_CONFIDENCE`, `MIN_ENTRY_PRICE`, `SESSION_MAX_LOSS_USD`, `SPORT`.
- Alphabetical sort confirmed — deterministic.
- `python -m py_compile bot_core.py` — PASS.
- Restart required — correctly noted.

## Why this matters for the next task

`STARTUP_PROOF_BLOCK_001` will emit `config_hash` in the startup log. With this fix applied, that hash now changes whenever any of the 15 gate-critical vars change. The proof block will be trustworthy. Without this fix first, the proof block would have been a misleading artifact.

## File locks released

- `bot_core.py` — RELEASED

## Next task

**`STARTUP_PROOF_BLOCK_001`** — file locks are clear. Activate immediately.

## Manager judgment

Close `CONFIG_HASH_INPUTS_FIX_001` to DONE.
Dispatch `STARTUP_PROOF_BLOCK_001`.
