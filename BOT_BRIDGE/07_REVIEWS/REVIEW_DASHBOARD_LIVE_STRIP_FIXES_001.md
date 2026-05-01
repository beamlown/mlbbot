# REVIEW_DASHBOARD_LIVE_STRIP_FIXES_001

Decision: **APPROVED**

Date: 2026-04-10

---

## Summary

All 6 sub-fixes implemented correctly in a single clean commit (7b33f18). Diff verified against task spec — every line matches the brief exactly. Only `dashboard.html` was touched (7 insertions, 2 deletions). No restart required.

---

## Acceptance criteria

| # | Criterion | Status | Notes |
|---|---|---|---|
| 1 | Only `dashboard.html` changed | PASS | `git show --stat 7b33f18` — one file, +7/-2 |
| 2 | `id="live-committed"` added to LIVE tab Capital Committed tile | PASS | Line 425 in current file |
| 3 | `live-committed` bound in state update function (renderState) | PASS | Line 670 — `if ($('live-committed')) $('live-committed').textContent = '$' + fmt2(br.capital_committed ?? 0)` |
| 4 | Module-level `let _availableCash = 0;` declared | PASS | Line 641 |
| 5 | `_availableCash` populated from `br.available_cash` in renderState | PASS | Line 671 — immediately after cash-committed bind |
| 6 | MTM bankroll in SSE handler: `_availableCash + live_equity_total` | PASS | Lines 1045-1046 inside `if (payload?.live_equity_total != null)` block |
| 7 | Stale feed wording is `'Market feed live · prices stale'` | PASS | Line 1053 — no recency clock, no contradiction |

---

## Scope compliance

- Allowed: `dashboard.html` — only file changed ✓
- `dashboard_server.py` not touched ✓
- No process restart performed (not required — browser hard-refresh sufficient) ✓

---

## Implementation notes

- The task brief referred to `updateState(s)` but the actual function in the codebase is `renderState(s)`. Worker used the correct in-code name. Semantically identical.
- MTM bankroll fallback is correct: `renderState()` sets `kpi-bankroll` to `br.current` (cost-basis) on state poll. The SSE handler then overwrites it with MTM as soon as any `positions_mark` event arrives. On SSE disconnect, the fallback value persists until SSE reconnects — acceptable behavior per task spec.
- `live-committed` uses a `$('live-committed')` null-guard (`if (...)`) — correct, defensive pattern matching the task spec.

---

## Verification

Verified statically via `git show 7b33f18`. Runtime verification (browser hard-refresh, confirmed committed tile populates, bankroll shows MTM, stale wording correct) is the operator's responsibility post-deploy — no restart needed.

---

## Rollback

`git revert 7b33f18` or `git checkout HEAD~1 -- sports_bot_v2/dashboard.html`. No server restart needed for rollback either.
