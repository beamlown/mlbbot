# CLAUDE_STATUS.md — Manager Status Snapshot
## Last reconciled: 2026-04-11 — Track A complete. Track B: EDGE_BASELINE + MODEL_SIGNAL_QUALITY both DONE. Confidence inversion is artifact. High-confidence exit damage is the live concern. Waiting on post-restart trade accumulation for CLEAN_RUNTIME_WINDOW_AUDIT_001 (n≥30 required).

---

## System State

### Launcher
- `launch_all.py` — singleton guard active (SINGLE_STACK_LAUNCH_GUARD_001 DONE)
- 4 children managed: `shadow_engine`, `bot_core`, `dashboard` (port 8900), `resolution_watcher`

### sports_bot_v2 (paper bot)
- Mode: LIVE TRADES ACTIVE
- Bridge: ENABLED (`ENABLE_MODEL_BRIDGE = True`)
- **Clean restart confirmed 2026-04-11** — config_hash `f87077f219dd`, all gates correct
- **Confidence gate: LIVE** — MIN_ENTRY_CONFIDENCE=0.65, 7 rejections confirmed in log
- **Min entry price gate: LIVE** — MIN_ENTRY_PRICE=0.22
- **Post-restart trades: 0** (n=0 since restart as of end of 2026-04-11)
- All Track A patches active: cooldown persistence, session PnL, dupe-slug fix, gap_stop session ban, slug cap

### Gate configuration (verified from STARTUP_PROOF log line)
```
MIN_ENTRY_CONFIDENCE: 0.65
MIN_ENTRY_PRICE:      0.22
MIN_CONFIDENCE:       0.25
MAX_CONCURRENT_TRADES: 3
MAX_TRADES_PER_MARKET: 1
LATE_INNING_BLOCK:    7
AUTO_STOP_LOSS_PCT:   0.12
LOOP_SECONDS:         30
```

### Dashboard
- Running on port 8900
- Side semantics: FIXED (POSITION_SIDE_SEMANTICS_MERGE_FIX_001 DONE)
- Mark fallback reliability: FIXED (MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001 DONE)
- At-bat upgrade: LIVE

### mlb_model
- Authority: clean (execution_guard.py deleted)
- Producing recs via recommendation_api.py
- Shadow log: `C:\Users\johnny\Desktop\mlb_model\logs\shadow_recommendations.jsonl`
  - ~63,000 entries, 18,760 BUY_YES/BUY_NO recs, 44,285 NO_TRADE recs

---

## Edge Proof Status (Track B)

| Criterion | Status | Key finding |
|-----------|--------|-------------|
| E1 — positive net expectancy | **FAIL** | -$91.13 net, avg -$0.33/trade |
| E2 — win rate > break-even | **MARGINAL FAIL** | 26.2% actual vs 26.7% required |
| E3 — not single-slug concentrated | **FAIL** | lad-tor = +$630.79, explains all positive offset |
| E4 — not single-trade concentrated | **FAIL** | top 5 = +$1,111 vs -$91 total; ex-top-5 = -$1,202 |
| E5 — clean-runtime window | **DEFERRED** | n=0 post-restart |
| E6 — confidence predictive | **FAIL** (revised) | Inversion is outlier artifact. High-confidence failure is exit-damage: stop_loss -$587 + gap_stop -$683 in 0.60-0.65 bucket |
| E7 — gated universe edge | **DEFERRED** | n=5, -$59.77 |
| E8 — beats random-side baseline | **UNRESOLVED** | proxy only, needs proper audit |

**Overall verdict: NO PROVEN EDGE.**

---

## Active Tasks

_(none — waiting on post-restart trade accumulation)_

## Queued Tasks

| task_id | status | unlock condition |
|---------|--------|-----------------|
| CLEAN_RUNTIME_WINDOW_AUDIT_001 | DEFERRED | Post-restart n≥30 trades |

---

## Open Items (not tasks)

| Item | Severity | Notes |
|------|----------|-------|
| Post-restart trade accumulation | ONGOING | n=0 as of 2026-04-11. E5/E7 cannot be evaluated until n≥30. |
| BUY_YES/BUY_NO structural asymmetry | UNDER INVESTIGATION | +$464 vs -$555 gap — MODEL_SIGNAL_QUALITY_AUDIT_001 will characterize |
| NEAR_RESOLUTION_CONFIDENCE_SUPPRESSOR_001 | BACKLOG | Model-side fix in recommendation_api.py — do not open until audits complete |
| Polymarket user/fill stream | BLOCKED | Requires apiKey, secret, passphrase in .env |

---

## Completed Track A (all patches live as of 2026-04-11 restart)

| Task | Outcome |
|------|---------|
| RESTART_CONFIG_HASH_VERIFY_001 | PASS — config_hash f87077f219dd confirmed |
| POST_GAP_STOP_SAME_SIDE_SESSION_BAN_001 | APPROVED — session ban after gap_stop live |
| SESSION_MARKET_TRADE_CAP_001 | APPROVED — MAX_SLUG_ENTRIES_SESSION=3 live |
| SINGLE_STACK_LAUNCH_GUARD_001 | APPROVED — post-sweep bot.pid guard live |
| STARTUP_PROOF_BLOCK_001 | APPROVED — STARTUP_PROOF log line live |
| LATE_INNING_BLOCK_WIRING_FIX_001 | APPROVED — LATE_INNING_BLOCK=7 live |
| CONFIG_HASH_INPUTS_FIX_001 | APPROVED — 15-var hash live |
| All prior Track A patches | APPROVED and LIVE |

## Completed Track B

| Task | Outcome |
|------|---------|
| MODEL_SIGNAL_QUALITY_AUDIT_001 | APPROVED 2026-04-11 — Confidence inversion is artifact (4 outlier trades). High-confidence weakness confirmed but is exit-damage, not direction inversion. BUY_NO advantage not yet structurally proven. |
| EDGE_BASELINE_AND_EXPECTANCY_AUDIT_001 | APPROVED 2026-04-11 — NO PROVEN EDGE. E1-E4 FAIL. E5/E7 DEFERRED. E6 revised by MODEL_SIGNAL_QUALITY_AUDIT_001. |
| NEAR_RESOLUTION_CONFIDENCE_SANITY_AUDIT_001 | APPROVED 2026-04-11 — root cause B confirmed (edge inflation). MIN_ENTRY_PRICE=0.22 is primary gate. |
