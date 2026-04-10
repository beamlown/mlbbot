# CLAUDE_CATCHUP_BRIEF

Claude was unavailable during a major incident + dashboard recovery cycle.

## What happened while Claude was gone
- A duplicate-entry incident was investigated and traced to duplicate runtime/process topology plus missing live DB unique open-slug protection.
- The live DB path was proven, duplicate open rows were remediated, and the unique index was created.
- Process topology was stabilized and state alignment was re-verified.
- After incidents were contained, dashboard work resumed and multiple passes tightened truth ownership, hierarchy, accounting clarity, and baseball-monitor feel.
- A fresh `dashboard_v2.html` shell was then built side-by-side instead of replacing production.

## What is fixed
- duplicate writer/process incident contained
- duplicate open rows remediated
- unique open-slug DB index created
- DB / `/api/trades` / `/api/state` alignment recovered in final verification
- production dashboard truth layer improved

## What is still broken or incomplete
- production dashboard still may not fully satisfy the desired baseball-monitor experience
- `dashboard_v2.html` exists but still needs explicit verification before being trusted as staging-ready
- final premium UX/design polish still remains open

## What is currently stable
- truth model: main positions = real paper trades only
- shadow = diagnostics only
- canonical open-position count model in dashboard layer
- accounting improvements exist and should not regress
- V2 shell exists without touching production page

## What must not regress
- no shadow-only main positions
- no duplicate writer topology
- no duplicate open-row behavior
- no loss of truthful accounting fields
- no fallback to trade-log-first hierarchy

## Recommended next work order
- Verification-only pass on `dashboard_v2.html` against live endpoints and live truth model, then decide whether it is good enough for Claude polish later.

## Latest Completed Task
- task id: DASHBOARD_V2_001
- result: Built a fresh `dashboard_v2.html` side-by-side as a game-first, position-first, truth-safe shell using `/api/state`, `/api/trades`, `/api/games`, and `/api/mlb-shadow`, without modifying the current production dashboard.
- architecture/truth/operations impact: Added a new staging frontend shell only; no production replacement, no truth-model change, no ops change.
- what Claude should do next when it returns: Verify whether V2 is a strong enough architectural base; if yes, focus on premium polish instead of rebuilding structure from scratch.
