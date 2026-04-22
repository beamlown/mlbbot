# REVIEW_EXECUTION_RISK_MONITOR_001

**Decision: APPROVED**
**Reviewed: 2026-04-10**

---

## Scope check

- Allowed files: `bot_core.py`, `core/risk.py`. Only `bot_core.py` modified. ✓
- `git diff --name-only` shows `sports_bot_v2/bot_core.py` only. ✓
- `core/risk.py` not modified — no changes needed there. ✓
- No TP/SL thresholds changed. ✓
- No dashboard or paper_exec touched. ✓

---

## Invariant evaluation

| Rule | Verdict | Evidence |
|------|---------|----------|
| EXIT_NEVER_SILENTLY_SKIPS | ✓ FIXED | After `check_exit()` returns `(False, "")`, checks `ob.bid_yes/bid_no` for None. Emits `logger.warning("Exit check skipped trade=%d ... reason=empty_ob")` |
| EXIT_ALWAYS_LOGS_CLOSE | ✓ CONFIRMED | `CLOSE` logger.info present on normal close path and market_resolved path. All exit reasons logged with trade.id, slug, reason, pnl. |
| STALE_OB_DOES_NOT_BLOCK_STOP_LOSS | ✓ FIXED (warning) | When held_bid=None, parses ts_open, computes stale_secs. If > STALE_OB_WARN_SECONDS (default 300s), emits WARNING. Forced exit not implemented per task spec ("warning is mandatory"). `STALE_OB_WARN_SECONDS` env var added. |
| DUMMY_MARKET_IS_FLAGGED | ✓ FIXED | One-liner `mkt = ... or _dummy_market(trade)` replaced with explicit None check. `logger.warning("Exit using dummy market for trade=%d market_id=%s — no live discovery match")` fires when `_market_by_id()` returns None. |
| COOLDOWNS_LOGGED_CONSISTENTLY | ✓ CONFIRMED | Cooldowns: near_resolution=600s, stop_loss=1800s, gap_stop=3600s. No cooldown on take_profit, trailing_stop, market_resolved, time_exit. Pattern consistent. |
| EXIT_LOOP_ERROR_SURFACED | ✓ FIXED | `logger.warning("Exit check error trade=%s: %s")` → `logger.error("Exit check error trade=%d: %s", trade.id, e, exc_info=True)`. Full stack trace now captured. |

---

## Acceptance criteria

- [x] All 6 monitoring invariants enforced (4 fixed, 2 confirmed already present)
- [x] Empty OB / None held_price logs WARNING with trade.id and slug
- [x] _dummy_market usage logs WARNING with trade.id and market_id
- [x] Exit loop exception logged at ERROR with exc_info=True
- [x] `python -m py_compile bot_core.py` — PASS
- [x] `python -m py_compile core/risk.py` — PASS
- [x] Only allowed_files changed
- [x] No TP/SL threshold values changed

---

## Rollback

Changes are additive (new log statements, one env var). Reverting is straightforward — revert the 4 hunks in bot_core.py. No DB writes, no schema changes.
