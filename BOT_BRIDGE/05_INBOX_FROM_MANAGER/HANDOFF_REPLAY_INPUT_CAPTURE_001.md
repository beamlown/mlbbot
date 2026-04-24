<!-- writer: manager, task_id: REPLAY_INPUT_CAPTURE_001, patch_id: pending, written_at: 2026-04-18T17:35:49Z, attempt: 1 -->

# HANDOFF: REPLAY_INPUT_CAPTURE_001

## Status
QUEUED — P2 phase, Replay Harness. Depends on TRADE_ATTRIBUTION_SCHEMA_001 + WIRING_001 being complete
(need the attribution schema stable so replay output can reconstruct the same
record shape).

## What you are doing
Ensure every discovery loop durably captures the inputs needed to re-run a
decision offline: orderbook snapshot, mark, model inputs, timestamp, event
identity. Existing `runtime/ob_snapshots/` may already do some of this — audit
and extend.

## Why this exists
A replay harness is only as good as the data it replays against. Without a
faithful capture, running an alternate config against history produces
garbage. This task is the data-layer prerequisite for the harness itself.

## Target files
- `C:\Users\johnny\Desktop\sports_bot_v2\bot_core.py` — main loop; inject
  capture call per iteration
- `C:\Users\johnny\Desktop\sports_bot_v2\core\state_hub.py` — if it's the
  central point for per-loop state, hook there instead
- `C:\Users\johnny\Desktop\mlb_model\integration\recommendation_api.py` — if
  model inputs are computed there, emit them
- New file: `C:\Users\johnny\Desktop\sports_bot_v2\core\replay_capture.py`
- Directory: `C:\Users\johnny\Desktop\sports_bot_v2\runtime\replay_captures\`

## Capture record schema

One JSONL file per day: `runtime/replay_captures/YYYY-MM-DD.jsonl`.

Each line:
```json
{
  "ts": "2026-04-18T14:32:05.123Z",
  "loop_id": "uuid-or-counter",
  "event_slug": "mlb-lad-col-2026-04-20",
  "registry_match": {"home": "LAD", "away": "COL", "status": "PRE_GAME", "is_live": false},
  "orderbook": {
    "bids": [[0.54, 1000], [0.53, 500]],
    "asks": [[0.55, 1200], [0.56, 800]]
  },
  "mark": {"value": 0.545, "source": "...", "ts": "..."},
  "model_inputs": {
    "home_team": "LAD",
    "away_team": "COL",
    "home_pitcher_id": 12345,
    "...": "everything the model needs to recompute"
  },
  "model_output": {"p_home": 0.58, "p_away": 0.42, "confidence": 0.58, "model_version": "..."},
  "discovery_decision": {"action": "SKIP_NOT_LIVE" | "RECOMMEND" | "TRADE" | "SKIP_NO_EDGE", "reason": "..."}
}
```

### What's captured vs what's derived
- Inputs captured: orderbook, mark, model_inputs, registry
- Outputs captured: model_output, discovery_decision
- On replay: inputs are re-fed to a target config; outputs are recomputed
  and compared. This means `model_inputs` must contain everything the model
  needs — audit the model to list them all, then capture them.

## Audit step (REQUIRED)
Before writing capture code:
1. Read `mlb_model/integration/recommendation_api.py` and trace which fields
   the model consumes.
2. List them in the result JSON under `model_input_fields_captured`.
3. If any field is not straightforwardly capturable (e.g., depends on network
   lookup), surface that as a limitation in the result and capture a
   snapshot-at-time reference instead.

## Retention
- No deletion in this task. Directory will grow — operator will add retention
  policy later.
- Small optimization: gzip files older than 7 days at startup (nice-to-have,
  not required).

## Existing `ob_snapshots/`
- Read `runtime/ob_snapshots/` first. Document what it contains and whether
  the replay capture can reuse or supersede it.
- If it's already capturing what we need, this task may reduce to "add the
  missing fields + standardize the schema."

## Output / deliverables
1. New `core/replay_capture.py` with `write_capture(record)` and JSONL append
2. Wiring in the main loop
3. Audit notes on existing ob_snapshots/ + model input fields
4. Sample capture file for a short live run (≥ 5 records)
5. Result JSON at `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_REPLAY_INPUT_CAPTURE_001.json`

## Result JSON fields required
```json
{
  "task_id": "REPLAY_INPUT_CAPTURE_001",
  "status": "ok",
  "capture_path_pattern": "runtime/replay_captures/YYYY-MM-DD.jsonl",
  "model_input_fields_captured": ["..."],
  "existing_ob_snapshots_analysis": "...",
  "sample_records_count": 5,
  "sample_file_path": "...",
  "limitations": ["..."],
  "files_changed": ["..."]
}
```

## Do NOT do
- Do not modify the model itself
- Do not modify discovery decision logic
- Do not change attribution schema (that was P0)
- Do not add the replay harness (that is REPLAY_HARNESS_BUILD_001)
- Do not add the sweep CLI (that is REPLAY_SWEEP_CLI_001)
- Do not delete anything from runtime/ob_snapshots/
- No real-money paths
