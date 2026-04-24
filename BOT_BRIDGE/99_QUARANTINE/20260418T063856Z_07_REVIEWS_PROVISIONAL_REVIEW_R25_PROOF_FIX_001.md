# PROVISIONAL_REVIEW_R25_PROOF_FIX_001

Decision: PROVISIONALLY_APPROVED

## What was proven

- The prior audit was correct about the mismatch.
- Current pre-fix behavior in `_read_state()` returned:
  - `win_rate: 0.0`, `expectancy: 0.0` when there were no closed trades
  - the same zeroed metrics on DB error
- That behavior did **not** match the original DASH_014 task spec, which required `win_rate` to be `null` when no closed trades exist and implied error cases should avoid ambiguous fake zero-performance output.

## What changed

- Scope stayed inside `dashboard_server.py` only.
- `_read_state()` r25 block was minimally corrected so that:
  - empty sample -> `win_rate: null`, `expectancy: null`, `sample_size: 0`
  - DB error -> `win_rate: null`, `expectancy: null`, zero counts, explicit `error` field
  - non-empty sample -> computed values preserved
- Loss counting now matches the original DASH_014 task text: `pnl <= 0` counts as a loss.

## What did not change

- No TP/SL logic changed.
- No dashboard HTML changed.
- No unrelated server logic changed.

## Provisional conclusion

`R25_PROOF_FIX_001` satisfies the narrow proof/fix goal and resolves the ambiguity identified by the audit.
