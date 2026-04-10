# REVIEW_SL_COOLDOWN_001

Decision: APPROVED

## Scope check
- Implementation confined to `sports_bot_v2/bot_core.py` in the exit-loop cooldown block.
- No edits to `risk.py`, `core/risk.py`, or unrelated files.

## What changed
- Kept existing `near_resolution` cooldown at 600s.
- Added `elif reason == "stop_loss"` cooldown of 1800s with explicit log text.
- Added `elif reason == "gap_stop"` cooldown of 3600s with explicit log text.
- Did not add cooldown for `take_profit` or `trailing_stop`.

## Verification
- `python -m py_compile sports_bot_v2/bot_core.py` passed.
- Exit block includes near_resolution + stop_loss + gap_stop cooldown handlers with expected durations.

## Notes
- Runtime log confirmation requires bot restart and a qualifying live exit event.
