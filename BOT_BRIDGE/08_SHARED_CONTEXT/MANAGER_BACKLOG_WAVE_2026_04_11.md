# MANAGER BACKLOG WAVE — 2026-04-11

## Purpose
Second-wave backlog created after tonight's findings.
This does **not** replace tomorrow's first-wave queue.
Tomorrow still starts with restart/config verification and the already-queued first-wave tasks.

## Decision frame
Per BOT_BRIDGE doctrine:
- Track A runtime truth stays ahead of Track B strategy work when activation proof is weak.
- Read-only audits stay ahead of speculative fixes when root cause is not pinned down.
- Repeated-loss containment is favored before upside-seeking strategy changes.

## Source-of-truth inputs used
- `08_SHARED_CONTEXT/OVERNIGHT_ANALYSIS_2026_04_10.md`
- `08_SHARED_CONTEXT/CLAUDE_TASK_BOARD.md`
- Tonight's restart/config-load findings already reflected in those documents

## Classification of newly captured gaps

### Runtime / config activation problems
1. `CONFIG_HASH_INPUTS_FIX_001`
2. `STARTUP_PROOF_BLOCK_001`
3. `SINGLE_STACK_LAUNCH_GUARD_001`

### Observability gaps
4. `TRADE_FORENSICS_SNAPSHOT_001`

### Containment / risk control gaps
5. `SESSION_SLUG_LOSS_CAP_001`
6. `MARKET_PRICE_SANITY_GATE_001`

### Model / data-freshness gaps
7. `GAME_STATE_FRESHNESS_AUDIT_001`

### Replay / counterfactual evaluation
8. `REPLAY_HARNESS_001`

## Ordered backlog after tomorrow's first-wave queue
1. `CONFIG_HASH_INPUTS_FIX_001`
2. `STARTUP_PROOF_BLOCK_001`
3. `SINGLE_STACK_LAUNCH_GUARD_001`
4. `TRADE_FORENSICS_SNAPSHOT_001`
5. `SESSION_SLUG_LOSS_CAP_001`
6. `GAME_STATE_FRESHNESS_AUDIT_001`
7. `MARKET_PRICE_SANITY_GATE_001`
8. `REPLAY_HARNESS_001`

## Why this order

### 1) CONFIG_HASH_INPUTS_FIX_001
Observed: runtime hash did not reflect important gate vars.
Proven: config verification was misleading tonight.
Why first in backlog: restart truth stays weak until the hash actually means something.

### 2) STARTUP_PROOF_BLOCK_001
Observed: no single startup proof block existed.
Proven: operators could not see one authoritative statement of runtime identity and loaded gates.
Why second: once the hash inputs are real, startup proof can expose them cleanly.

### 3) SINGLE_STACK_LAUNCH_GUARD_001
Observed: dual/live mixed stack confusion was plausible.
Likely: some restart ambiguity came from process-topology uncertainty.
Why third: narrow operational protection against mixed stacks, isolated to launcher path.

### 4) TRADE_FORENSICS_SNAPSHOT_001
Observed: trade-level forensic context is too weak.
Proven: tonight's bad entries required manual reconstruction from scattered evidence.
Why fourth: strengthens later audit and replay without changing strategy.

### 5) SESSION_SLUG_LOSS_CAP_001
Observed: repeated-market damage can outpace count-only controls.
Likely: slug-level dollar containment would have stopped some heavy damage earlier.
Why fifth: containment fix, but after first-wave count cap because both overlap the same gate surface.

### 6) GAME_STATE_FRESHNESS_AUDIT_001
Observed: irrational late-game entries suggest stale or insufficient game-state may be involved.
Not yet proven: whether freshness failure is the main cause.
Why sixth: read-only audit before deeper model-side fixes.

### 7) MARKET_PRICE_SANITY_GATE_001
Observed: near-zero and near-one irrational entries need explicit handling.
Likely: a hard containment gate is useful regardless of model quality.
Why seventh: keep it distinct from the near-resolution/model freshness audits so the rationale stays clean.

### 8) REPLAY_HARNESS_001
Observed: new guardrails need replay-first evidence.
Why eighth: valuable, but dependent on better observability and not required for tomorrow morning's trust restoration.

## File-overlap and lock notes
- `bot_core.py` overlap cluster:
  - `STARTUP_PROOF_BLOCK_001`
  - `TRADE_FORENSICS_SNAPSHOT_001`
  - `SESSION_MARKET_TRADE_CAP_001` (first-wave)
  - `POST_GAP_STOP_SAME_SIDE_SESSION_BAN_001` (first-wave)
  - `SESSION_SLUG_LOSS_CAP_001`
  - `MARKET_PRICE_SANITY_GATE_001`
- `core/risk.py` overlap cluster:
  - `CONFIG_HASH_INPUTS_FIX_001`
  - `STARTUP_PROOF_BLOCK_001`
  - `SESSION_MARKET_TRADE_CAP_001` (first-wave)
  - `SESSION_SLUG_LOSS_CAP_001`
  - `MARKET_PRICE_SANITY_GATE_001`
  - `REPLAY_HARNESS_001` (if helper reuse is needed)
- `launch_all.py` isolated:
  - `SINGLE_STACK_LAUNCH_GUARD_001`
- Model-side read-only cluster:
  - `NEAR_RESOLUTION_CONFIDENCE_SANITY_AUDIT_001` (first-wave)
  - `GAME_STATE_FRESHNESS_AUDIT_001`

## Manager guidance
- Do not activate any second-wave backlog task before tomorrow's first-wave queue unless the first-wave plan is explicitly changed.
- Prefer `GAME_STATE_FRESHNESS_AUDIT_001` before any speculative deeper model patch.
- Treat `MARKET_PRICE_SANITY_GATE_001` as a containment layer, not proof that model/data issues are solved.
- Treat `STARTUP_PROOF_BLOCK_001` as source-only until observed live after restart.
