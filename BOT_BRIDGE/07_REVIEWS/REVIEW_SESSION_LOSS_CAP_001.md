# REVIEW_SESSION_LOSS_CAP_001

**Decision: APPROVED**
**Reviewed: 2026-04-10**

---

## Scope check

- Only `bot_core.py` modified — within `allowed_files` (brief also permitted `core/risk.py` but worker chose the cleaner bot_core.py-only path, which is explicitly acceptable per brief). ✓
- `git diff --name-only` shows only `sports_bot_v2/bot_core.py`. ✓
- Rollback possible via `git revert`. ✓

## What changed

- `SESSION_MAX_LOSS_USD` and `DAILY_MAX_LOSS_USD` env reads added at `bot_core.py:36-37`. Default `0` keeps caps disabled — backward compatible. ✓
- `_session_start_ts` set at startup (module-level, not a DB write). ✓
- `_session_loss_exceeded()` helper at `bot_core.py:267` — computes session and daily realized PnL from closed trades, returns True and logs ERROR if cap hit. ✓
- Gate wired into entry flow at `bot_core.py:380` — blocks local and model-bridge entries when cap is hit; exit checks continue running. ✓

## Acceptance criteria

- Per-session max loss cap: present and env-configurable ✓
- Daily max loss cap: present and env-configurable ✓
- Caps disabled when env vars = 0 (backward compatible): confirmed via logic trace ✓
- Open positions not closed when cap fires: confirmed ("exits continue to run") ✓
- No DB modifications when cap fires ✓
- No hardcoded values ✓
- py_compile passed ✓
- Only allowed files touched ✓

## Notes

Both HIGH-severity gaps from RISK_PIPELINE_AUDIT_REPORT_001.md (no per-session max loss cap, no daily max loss cap) are now closed. Caps are currently disabled by default (0) — operator must explicitly set values in `.env` to activate.
