# HANDOFF — LATE_INNING_BLOCK_WIRING_FIX_001

## What you are doing

Wiring a late-inning entry block into the live recommendation-to-entry path. This is a narrow, surgical fix. The config already exists (`LATE_INNING_BLOCK=7` in `.env`). The inning data already exists on the live signal/recommendation object. The only thing missing is the enforcement node — no gate currently reads these two things together.

## Why this task exists

`LATE_INNING_BLOCK_WIRING_VERIFY_001` proved the block is inert:
- `.env` has `LATE_INNING_BLOCK=7` ✓
- `inning` context is attached to the recommendation object ✓
- `recommendation_api.py` does not read `LATE_INNING_BLOCK` ✗
- `model_bridge.py` does not enforce a late-inning block ✗
- `risk.py` `check_entry_gates()` has no inning parameter and no late-inning logic ✗
- `bot_core.py` does not pass inning into `check_entry_gates()` ✗

The bot has been entering on games in inning 8, 9, and later — buying YES tokens on teams down 1–2 runs late in the game — because nothing stops it. This task exists to close that gap, not to redesign how the model thinks about game state.

## What the live path looks like

```
recommendation_api.py  →  model_bridge.py  →  bot_core.py  →  risk.check_entry_gates()
                                                     ↑
                                              fix lands here
                                         (pre-gate or gate param)
```

## What to do

**Step 1 — Confirm the inning field name.**
In `bot_core.py`, find the variable that holds the signal/intent after the bridge loop passes it. Check `core/types.py` for the `Signal` class definition. You need the exact attribute name for inning (likely `signal.inning` or `signal.game_state.inning` or similar).

**Step 2 — Choose your implementation surface.**

**Option A — Pre-gate in bot_core.py (keeps risk.py signature clean):**
Add an explicit check immediately before the `check_entry_gates()` call:
```python
_LATE_INNING_BLOCK = int(os.getenv("LATE_INNING_BLOCK", "0"))
_sig_inning = getattr(signal, "inning", None)
if _LATE_INNING_BLOCK > 0 and _sig_inning is not None and _sig_inning >= _LATE_INNING_BLOCK:
    logger.info(
        "BRIDGE GATE REJECT [late_inning_block] slug=%s inning=%s>=%s",
        market.slug, _sig_inning, _LATE_INNING_BLOCK,
    )
    _bridge_consumed_slugs.add(market.slug)
    continue
```

**Option B — Gate parameter in risk.py (gate logic consolidated):**
Add `LATE_INNING_BLOCK = int(os.getenv("LATE_INNING_BLOCK", "0"))` at module level in `risk.py` alongside existing env reads. Add optional `inning: int | None = None` parameter to `check_entry_gates()`. Add the block as the first check in the waterfall:
```python
if LATE_INNING_BLOCK > 0 and inning is not None and inning >= LATE_INNING_BLOCK:
    return False, [f"late_inning_block:{inning}>={LATE_INNING_BLOCK}"]
```
Then update the `bot_core.py` call site to pass `inning=getattr(signal, "inning", None)`.

**Pick one option. Justify your choice. Do not implement both.**

**Step 3 — None-safety.**
If `inning` is None (pre-game, missing data, API gap), do NOT block. This gate must be a strict no-op when inning is unavailable.

**Step 4 — py_compile.**
Run `python -m py_compile bot_core.py` and `python -m py_compile core/risk.py` (if modified). Both must PASS.

## What NOT to do

- Do not touch `recommendation_api.py` or `model_bridge.py`
- Do not add new data fields to the Signal or intent objects
- Do not mix this with CONFIG_HASH_INPUTS_FIX_001 or STARTUP_PROOF_BLOCK_001 edits
- Do not refactor unrelated gate logic
- Do not add any strategy improvements beyond this single block

## File locks

This task touches `bot_core.py` and/or `core/risk.py`. Do not activate while any other task locking these files is ACTIVE.

## Sequencing note

This task is **ACTIVE NOW** — it runs before `CONFIG_HASH_INPUTS_FIX_001` and `STARTUP_PROOF_BLOCK_001`. Those two tasks are queued behind it and cannot activate until this one is APPROVED and its file locks on `bot_core.py` / `core/risk.py` are cleared.

## Result file

Write your result to:
`C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_LATE_INNING_BLOCK_WIRING_FIX_001.json`

Required fields in result:
- `task_id`
- `files_changed` (list)
- `option_chosen` ("A" or "B") and one-sentence justification
- `inning_field_name` — exact attribute used
- `diff_summary` — key lines added
- `log_format` — what the BRIDGE GATE REJECT message looks like
- `py_compile_results` — PASS/FAIL for each changed file
- `restart_required`
- `acceptance_criteria_met` — one line per criterion
