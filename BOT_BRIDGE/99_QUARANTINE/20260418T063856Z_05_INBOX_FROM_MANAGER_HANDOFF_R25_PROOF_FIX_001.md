# HANDOFF - R25_PROOF_FIX_001
## Prove and minimally correct r25 empty/error behavior

Current behavior observed in `dashboard_server.py`:
- `_read_state()` always returns an `r25` object.
- If there are no closed trades, it returns `win_rate: 0.0` and `expectancy: 0.0`.
- If the DB query fails, it also returns a zeroed `r25` object.

Intended behavior from DASH_014 task + handoff:
- `r25` should report actual stats from the last 25 closed trades.
- If there are no closed trades, `win_rate` should be `null` and `expectancy` should be `null`.
- Error handling should not silently impersonate a real zero-performance sample.

Required action:
- Keep scope limited to the `_read_state()` r25 block in `dashboard_server.py`.
- Apply the smallest fix necessary.
- No unrelated server or dashboard changes.

Expected correction:
- Empty sample -> `win_rate: null`, `expectancy: null`, `sample_size: 0`
- DB error -> explicit fallback with null metrics, zero counts, and an error note for proof/debugging
- Preserve actual computed values for non-empty successful cases
