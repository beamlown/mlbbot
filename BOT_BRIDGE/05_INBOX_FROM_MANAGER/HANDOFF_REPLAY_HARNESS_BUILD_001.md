<!-- writer: manager, task_id: REPLAY_HARNESS_BUILD_001, patch_id: pending, written_at: 2026-04-18T17:35:49Z, attempt: 1 -->

# HANDOFF: REPLAY_HARNESS_BUILD_001

## Status
QUEUED — P2 phase, Replay Harness. Depends on REPLAY_INPUT_CAPTURE_001.

## What you are doing
Build the replay harness: given a date range + an alternate config (confidence
gate, edge threshold, sizing curve), re-run the model + decision pipeline
against captured inputs and emit a counterfactual trade set + attribution
summary.

## Why this exists
The bot currently learns at live speed — one session per day. Replay
multiplies velocity by ~100x: one week of captures + 10 configs = 70 sessions
of insight in minutes. But the harness is useless unless it's faithful;
that's why CAPTURE (001) must be solid first.

## Reference / possibly preexisting
A prior handoff `HANDOFF_REPLAY_HARNESS_001.md` exists in BOT_BRIDGE history.
Check whether it resulted in code already — look for `RESULT_REPLAY_HARNESS_001`
in `06_OUTBOX_FROM_WORKER/`. If partial work exists, build on it; do NOT
re-create a parallel module.

## Target files
- `C:\Users\johnny\Desktop\sports_bot_v2\tools\replay.py` — NEW
- `C:\Users\johnny\Desktop\sports_bot_v2\core\replay_harness.py` — NEW (logic)
- Reuse: `core/attribution.py` (from P0), `core/paper_exec.py` slippage path,
  `core/replay_capture.py` (from 001)

## Replay harness contract

```
replay.run(
    captures_dir: Path,
    start_date: date,
    end_date: date,
    config: ReplayConfig,
) -> ReplayResult
```

`ReplayConfig`:
- `confidence_gate: float`
- `edge_threshold_pct: float`
- `sizing: SizingCurve` (mirror the live sizing interface)
- `slippage_cents: float`
- `model_version: str` (allow pinning to a specific model version if model has versions)
- `name: str` (for identification in results)

`ReplayResult`:
- `config: ReplayConfig`
- `trades: list[ReplayedTrade]` — each with same attribution fields as real trades
- `summary`:
  - `n_trades`
  - `hit_rate`
  - `brier_score`
  - `log_loss`
  - `expected_edge_realized_pct` (sum of realized_pnl / sum of expected_edge * size)
  - `pnl_by_trade_class` (5 enum buckets)

## Replay algorithm

1. For each capture in date range:
   - Recompute model output from `model_inputs` (if we trust captured `model_output`, use it; but ideally recompute to allow model-version sweeps)
   - Apply config's confidence_gate + edge_threshold to decide TRADE vs SKIP
   - If TRADE: simulate fill via walk-the-book from captured orderbook +
     config.slippage_cents
   - Simulate exit: this is the tricky part
     - If next capture for the same event has resolved: use resolution
     - Else: simulate TP/SL against the price trajectory across subsequent
       captures
     - If no captures covering the full event: mark UNRESOLVED

2. Populate a `ReplayedTrade` with the same attribution schema as live
   (entry/exit probs, edge, fill px, trade_class).

3. Aggregate into `ReplayResult.summary`.

## Fidelity guards
- A replay trade that diverges from a matching real trade (same event, similar
  entry time, same config params) should produce near-identical attribution.
  Include a "fidelity check" mode: given a historical config, replay should
  produce trades within epsilon of the real ones. If not, the harness isn't
  faithful — surface the delta prominently.
- Model recomputation must pin model version; if a model update happened
  mid-range, split the replay across the version boundary.

## Output / deliverables
1. `core/replay_harness.py` with `ReplayConfig`, `ReplayResult`, `ReplayedTrade` dataclasses + core logic
2. `tools/replay.py` CLI entry point (minimal — full CLI is next task)
3. A "fidelity check" run against one past day that shows < 5% PnL divergence from real trades of the same config
4. Result JSON at `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_REPLAY_HARNESS_BUILD_001.json`

## Result JSON fields required
```json
{
  "task_id": "REPLAY_HARNESS_BUILD_001",
  "status": "ok",
  "harness_module": "core/replay_harness.py",
  "cli_entry_point": "tools/replay.py",
  "fidelity_check": {
    "date_replayed": "2026-04-15",
    "n_real_trades": 0,
    "n_replay_trades": 0,
    "pnl_divergence_pct": 0.0,
    "notes": "..."
  },
  "prior_replay_harness_handoff_reused": true,
  "files_changed": ["..."]
}
```

## Do NOT do
- Do not build the sweep CLI (that is REPLAY_SWEEP_CLI_001)
- Do not change the model
- Do not change the attribution schema
- Do not modify bot_core live paths
- Do not touch BOT_BRIDGE
- No real-money paths

---
## RETRY CONTEXT (auto-generated — attempt 2)

A previous run failed on this task. Before you start, read this:

- prior status: `blocked`
- prior summary: Cannot proceed: prerequisite task REPLAY_INPUT_CAPTURE_001 is QUEUED and incomplete. The replay harness algorithm requires captured model inputs, orderbook snapshots, and decision logs from runtime/replay_captures/ which REPLAY_INPUT_CAPTURE_001 should produce.
- prior run id: `RUN_7A3649BFA732`

### What went wrong
The previous worker did not produce a RESULT for **REPLAY_HARNESS_BUILD_001**. Common causes: (a) the worker drifted to a different task, (b) the worker never wrote `RESULT_REPLAY_HARNESS_BUILD_001.json`, (c) the worker exited before completing the scope.

### What to do differently this attempt
1. Work ONLY on `REPLAY_HARNESS_BUILD_001`. Ignore every other task name you see.
2. Write your result to `BOT_BRIDGE/06_OUTBOX_FROM_WORKER/RESULT_REPLAY_HARNESS_BUILD_001.json` and NO other file.
3. If the scope is unclear, emit `status: blocked` with a specific question.
   Do NOT substitute a different task you think you know.

### Prior stdout tail (for diagnosis)
```

3. **No runtime/replay_captures directory exists** — no captured input data available.

The HANDOFF specifies: "The replay harness algorithm requires captured model inputs, orderbook snapshots, and decision logs from runtime/replay_captures/ which [REPLAY_INPUT_CAPTURE_001] should produce."

Without the captured data and the replay_capture module, I cannot build the requested harness. The HANDOFF is clear: this task depends on REPLAY_INPUT_CAPTURE_001.
[tool→ Write] file_path=C:\Users\johnny\Desktop\mlbbot\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_REPLAY_HARNESS_BUILD_001.json
[tool← 196B] File created successfully at: C:\Users\johnny\Desktop\mlbbot\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_REPLAY_HARNESS_BUILD_001.json (file state is current in your context — no need to Read it back)
[thinking] Good. I've written the blocked result. The task cannot be completed because the prerequisite REPLAY_INPUT_CAPTURE_001 has not been completed. The HANDOFF is clear about this dependency, and the requi…
Done. **REPLAY_HARNESS_BUILD_001 is BLOCKED** — its prerequisite task REPLAY_INPUT_CAPTURE_001 remains QUEUED and incomplete. The harness requires captured model inputs and decision logs (replay_capture.py module + runtime/replay_captures/ directory) which that task should produce. Result written to `RESULT_REPLAY_HARNESS_BUILD_001.json`.
[done] ok duration=45281ms turns=9
[usage] input=66 output=3638 cache_read=337684 cost_usd=0.0763
```
