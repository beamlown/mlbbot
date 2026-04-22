# REVIEW: SESSION_SLUG_LOSS_CAP_001
**Decision: APPROVED — 2026-04-17**
**Process note: PROCESS VIOLATION — task was in QUEUED state, not ACTIVE. Worker self-activated out of turn.**

## What happened

Worker executed this QUEUED task and delivered a result without manager activation. This mirrors the NEAR_RESOLUTION_CONFIDENCE_SUPPRESSOR_001 incident. Approval is on substance only — the implementation is correct.

## Acceptance criteria check

- ✅ Further entries on a slug are blocked after slug reaches configured session loss cap
- ✅ Threshold is configurable via `MAX_SLUG_LOSS_USD` env var (default 0 = disabled)
- ✅ Rejection logged in standard `BRIDGE GATE REJECT [check_entry_gates]` format
- ✅ Only `sports_bot_v2/bot_core.py` modified — no out-of-scope files
- ✅ `python -m py_compile` PASS (per result JSON)
- ✅ `core/risk.py` not modified (not required)

## Implementation review

**`_session_slug_loss_bans: set`** (line ~123):
- In-memory set tracking banned slugs for session
- Persisted to `state.json` as `session_slug_loss_bans`, restored on startup (lines ~403–411)

**Bridge gate logic** (two-part check, lines ~619–655):
1. Already-banned check: if `market.slug in _session_slug_loss_bans` → reject immediately
2. Cap evaluation: SQL `SUM(pnl_usd) WHERE pnl_usd < 0` on closed trades for slug. Comparison `_slug_loss <= -MAX_SLUG_LOSS_USD` is correct (losses are negative).
3. Exception wrapped — DB failure does not block entry (fail-open is appropriate here)

Gate is placed after gap_stop ban check and before entry count check. Correct ordering.

`_write_state()` includes `session_slug_loss_bans` in state JSON payload. Restore path handles empty/missing key safely.

## Restart required

`bot_core.py` is a runtime process. Restart required for this change to take effect. Default `MAX_SLUG_LOSS_USD=0` disables the cap until explicitly set.
