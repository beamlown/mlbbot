# REVIEW_EXIT_GAME_AWARE_002

Decision: APPROVED

## Scope check

- In-scope code change implemented in `sports_bot_v2/bot_core.py` only.
- Added a hold-to-resolution suppression gate immediately after `check_exit(...)` and before `if should_close:`.
- Suppression is limited to `reason == "near_resolution"`.
- Safe degradation is preserved with `and resolved_markets` guard, so empty watcher state falls back to pre-watcher behavior.
- No timeout/cooldown changes for the hold path.

## Verification

- `python -m py_compile sports_bot_v2\\bot_core.py` passed.
- `git diff --name-only` shows only `sports_bot_v2/bot_core.py` for code changes.
- `findstr /n /c:"HOLD trade=" sports_bot_v2\\bot_core.py` confirms hold log line present.
- `findstr /n /c:"near_resolution" sports_bot_v2\\bot_core.py` confirms both new suppression gate and existing cooldown block remain.

## Notes

- HOLD log text uses a hyphen (` - `) instead of an em dash to match workspace punctuation conventions.
- Behavior is conservative: existing exits remain unchanged except near_resolution suppression when watcher is active and current market is not yet resolved.
