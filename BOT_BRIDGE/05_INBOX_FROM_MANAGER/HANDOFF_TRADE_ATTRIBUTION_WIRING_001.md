<!-- writer: manager, task_id: TRADE_ATTRIBUTION_WIRING_001, patch_id: pending, written_at: 2026-04-18T17:35:49Z, attempt: 1 -->

# HANDOFF: TRADE_ATTRIBUTION_WIRING_001

## Status
QUEUED — P0 phase, Attribution Spine. Depends on TRADE_ATTRIBUTION_SCHEMA_001.

## What you are doing
Wire the entry, exit, and resolution code paths so every new paper trade
populates the attribution columns added by the schema task. Backfill existing
trades where the data can be reconstructed from logs/DB.

## Why this exists
Schema alone does nothing. Every trade entry must snapshot model_prob,
market_prob, edge. Every exit must record exit_reason and closing probs. On
market resolution, the resolved_winner + model_side_was_right + trade_class
must be computed and stored.

## Target files
- `C:\Users\johnny\Desktop\sports_bot_v2\bot_core.py` — entry hook
- `C:\Users\johnny\Desktop\sports_bot_v2\core\paper_exec.py` — fill + exit hooks
- `C:\Users\johnny\Desktop\sports_bot_v2\core\risk.py` — exit reasons sourced here (TP, SL, caps)
- `C:\Users\johnny\Desktop\mlb_model\integration\resolution_watcher.py` — resolution hook
- `C:\Users\johnny\Desktop\sports_bot_v2\tools\backfill_attribution.py` — NEW: backfill script

## Wiring points

### 1. Entry (bot_core.py + paper_exec.py)
When a trade is opened, capture:
- `entry_model_prob` — the model recommendation used to decide
- `entry_market_prob` — the orderbook-implied prob at that moment (use the same
  mark-source authority as the rest of the bot — see prior
  `MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001` work)
- `expected_edge_pct` = entry_model_prob − entry_market_prob
- `actual_fill_px`, `actual_fill_size`

Persist via `core/attribution.TradeAttribution` + the JSONL writer AND write
back to the `trades` row (same transaction as trade insert).

### 2. Exit (paper_exec.py + risk.py)
When a trade is closed before resolution:
- `exit_reason` — must be one of the enum; the caller (risk.py for TP/SL/caps,
  paper_exec.py for MANUAL) passes it explicitly
- `exit_model_prob`, `exit_market_prob` — snapshot at exit
- `hold_seconds` = exit_ts − entry_ts
- `realized_pnl` — from the existing P&L path

### 3. Resolution (resolution_watcher.py)
When a market resolves:
- `resolved_winner` — YES/NO / team name per market schema
- `model_side_was_right` — bool
- `trade_class` — call `attribution.classify_trade(...)`
- If trade was held through resolution: `exit_reason = RESOLUTION`, set
  `exit_model_prob`/`exit_market_prob` to their last seen values, set
  `hold_seconds`

### 4. Backfill (new script)
`tools/backfill_attribution.py`:
- Reads existing trades that have NULL attribution columns
- For each: best-effort reconstruct from `logs/trade_forensics_baseball.jsonl`,
  `runtime/ob_snapshots/`, and existing DB rows
- Sets `trade_class = UNRESOLVED` and `attribution_version = 0` for rows where
  reconstruction is incomplete (so we can distinguish reliable vs best-effort)
- CLI: `python -m tools.backfill_attribution [--dry-run]`
- Idempotent

## Edge cases
- Trade opened but never filled → no attribution row written
- Trade resolved before exit logic runs → `exit_reason = RESOLUTION` wins
- `expected_edge_pct` with non-finite / missing probs → write NULL, don't crash
- Duplicate resolution updates → idempotent UPSERT on trade_id

## Output / deliverables
1. Modified files above with wiring
2. New backfill script `tools/backfill_attribution.py`
3. Result JSON at `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_TRADE_ATTRIBUTION_WIRING_001.json`

## Result JSON fields required
```json
{
  "task_id": "TRADE_ATTRIBUTION_WIRING_001",
  "status": "ok",
  "wired_entry": "file:line",
  "wired_exit": "file:line",
  "wired_resolution": "file:line",
  "backfill_script_path": "...",
  "existing_trades_count": 0,
  "backfilled_count": 0,
  "unreconstructible_count": 0,
  "files_changed": ["..."]
}
```

## Do NOT do
- Do not modify the schema (that was task 001)
- Do not add new dashboard panels (that is ATTRIBUTION_DASHBOARD_001)
- Do not change mark-source authority — use existing resolver
- Do not change entry/exit decision logic, only observation/record
- Do not alter bankroll/sizing
- No real-money code paths

---
## RETRY CONTEXT (auto-generated — attempt 4)

A previous run failed on this task. Before you start, read this:

- prior status: `fail`
- prior summary: (no RESULT_JSON emitted and no RESULT file written)
- prior run id: `RUN_5F316B4F353F`

### What went wrong
The previous worker did not produce a RESULT for **TRADE_ATTRIBUTION_WIRING_001**. Common causes: (a) the worker drifted to a different task, (b) the worker never wrote `RESULT_TRADE_ATTRIBUTION_WIRING_001.json`, (c) the worker exited before completing the scope.

### What to do differently this attempt
1. Work ONLY on `TRADE_ATTRIBUTION_WIRING_001`. Ignore every other task name you see.
2. Write your result to `BOT_BRIDGE/06_OUTBOX_FROM_WORKER/RESULT_TRADE_ATTRIBUTION_WIRING_001.json` and NO other file.
3. If the scope is unclear, emit `status: blocked` with a specific question.
   Do NOT substitute a different task you think you know.

### Prior stdout tail (for diagnosis)
```
**Backfill Script** (tools/backfill_attribution.py)
- Idempotent: only backfills trades with NULL attribution fields
- Reconstructs entry_model_prob from trade_forensics.jsonl
- Reconstructs entry_market_prob from actual_fill_px
- Maps reason_close → exit_reason enum values
- Infers resolved_winner/model_side_was_right from exit_px extremes
- Sets attribution_version=1 (reliable) if 5+ fields, else 0 (best-effort)
- Supports both baseball and basketball logs

Result JSON written to `BOT_BRIDGE/06_OUTBOX_FROM_WORKER/RESULT_TRADE_ATTRIBUTION_WIRING_001.json` with full implementation details.
[done] ok duration=87956ms turns=13
[usage] input=13277 output=12011 cache_read=520318 cost_usd=0.1950
```
