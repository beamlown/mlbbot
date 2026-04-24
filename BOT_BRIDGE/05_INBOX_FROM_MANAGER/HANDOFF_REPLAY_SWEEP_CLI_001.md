<!-- writer: manager, task_id: REPLAY_SWEEP_CLI_001, patch_id: pending, written_at: 2026-04-18T17:35:49Z, attempt: 1 -->

# HANDOFF: REPLAY_SWEEP_CLI_001

## Status
QUEUED — P2 phase, Replay Harness. Depends on REPLAY_HARNESS_BUILD_001.

## What you are doing
Build a CLI on top of the replay harness that sweeps multiple configs against
the same date range and prints a comparison table. This is the payoff task —
the operator uses this to choose which config to promote.

## Why this exists
The harness gives us one-config replay. The sweep CLI gives us N-config
replay in one invocation, with a ranked comparison table. This is what
actually multiplies learning velocity.

## Target files
- `C:\Users\johnny\Desktop\sports_bot_v2\tools\replay.py` — extend CLI
- `C:\Users\johnny\Desktop\sports_bot_v2\configs\` — NEW dir for YAML configs
- `C:\Users\johnny\Desktop\sports_bot_v2\configs\baseline.yaml` — example config
- `C:\Users\johnny\Desktop\sports_bot_v2\configs\gate_sweep.yaml` — example sweep

## CLI contract

```
python -m tools.replay [--single | --sweep] \
    --start YYYY-MM-DD \
    --end YYYY-MM-DD \
    --config PATH [--config PATH ...] \
    [--output results/sweep_YYYYMMDD_HHMMSS.json]
```

### Single mode
Runs one config, pretty-prints a summary + writes JSON.

### Sweep mode
- Accepts multiple `--config` paths OR a single sweep config that enumerates variants
- Runs each in parallel if possible (threads are fine; the harness is CPU-light)
- Prints a comparison table sorted by `realized_pnl` descending:

```
name                    n_trades  hit%   Brier  edge_realized%  pnl
---------------------------------------------------------------------
gate_0.60_edge_0.03     87        54.0   0.187  62.3             $412.30
gate_0.58_edge_0.02     142       52.1   0.191  48.7             $388.10
baseline                63        55.6   0.181  71.2             $350.20
gate_0.55_edge_0.01     201       50.2   0.201  34.1             $280.40
```

- Plus a `BEST/WORST BY` summary: best hit%, best Brier, best edge-realization,
  best pnl.

## Config YAML schema

```yaml
name: gate_0.60_edge_0.03
confidence_gate: 0.60
edge_threshold_pct: 0.03
slippage_cents: 2.0
sizing:
  type: flat
  size_pct: 0.01
model_version: current
```

Sweep config: same shape but each key can be a list, harness generates the cross product:
```yaml
name: gate_sweep
confidence_gate: [0.55, 0.58, 0.60, 0.62]
edge_threshold_pct: [0.01, 0.02, 0.03]
slippage_cents: 2.0
sizing:
  type: flat
  size_pct: 0.01
```

## Output files
- `results/sweep_TIMESTAMP.json` — full per-config ReplayResult serialized
- `results/sweep_TIMESTAMP.txt` — the comparison table (same as stdout)

## Performance target
- 7-day range × 10 configs must finish in < 2 minutes on operator's machine.
- If slower, report in result JSON + suggest where to optimize.

## Output / deliverables
1. Extended `tools/replay.py` with sweep mode
2. Two example YAML configs (`baseline.yaml`, `gate_sweep.yaml`)
3. Sample sweep output from a real 3–7 day range
4. Result JSON at `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_REPLAY_SWEEP_CLI_001.json`

## Result JSON fields required
```json
{
  "task_id": "REPLAY_SWEEP_CLI_001",
  "status": "ok",
  "cli_invocation_example": "python -m tools.replay --sweep --start 2026-04-11 --end 2026-04-17 --config configs/gate_sweep.yaml",
  "sample_sweep_summary": [
    {"name": "gate_0.60_edge_0.03", "n_trades": 87, "hit_pct": 54.0, "brier": 0.187, "pnl": 412.30}
  ],
  "runtime_seconds_7d_10config": 0,
  "output_artifacts": ["results/sweep_*.json", "results/sweep_*.txt"],
  "files_changed": ["..."]
}
```

## Do NOT do
- Do not modify the harness core (that was 002)
- Do not change the model
- Do not change attribution schema
- Do not modify bot_core live paths
- Do not touch BOT_BRIDGE contents
- Do not add result-visualization (dashboards) in this task — just CLI + JSON + text
- No real-money paths
