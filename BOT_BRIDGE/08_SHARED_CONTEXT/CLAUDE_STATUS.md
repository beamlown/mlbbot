# CLAUDE_STATUS.md — Manager Status Snapshot
## Last reconciled: 2026-04-12 — pitcher/bullpen hydration build reviewed. Chunked/resumable hydration completion is now the active data-foundation task.

---

## Current operating stance
- Runtime/config loading is fixed and runtime-proven.
- Execution plumbing is no longer the primary blocker.
- Strategy still has no proven edge.
- Confidence is structurally unreliable and not monotonic in the historical sample.
- Near-resolution failures are best explained by missing sanity logic plus recommendation-layer/model-core interaction, not stale-state alone.
- System remains paper-only / observation mode until rebuilt model quality is demonstrated.

---

## Completed rebuild audits/spec work
- MLB_DATA_INVENTORY_AUDIT_001
- MLB_MODEL_INPUT_PATH_AUDIT_001
- MLB_CONFIDENCE_CALIBRATION_AUDIT_001
- MLB_NEAR_RESOLUTION_SANITY_AUDIT_001
- MLB_DATA_GAP_MAP_001
- MLB_STATS_FOUNDATION_SPEC_001

---

## Review routing update
MLB_PITCHER_BULLPEN_HYDRATION_BUILD_001 received CHANGES REQUESTED.

Why:
- bounded pitcher/bullpen hydration was attempted
- process was terminated with SIGKILL before completion
- no trustworthy final canonical counts can be claimed
- updater must remain queued

Result:
- switch to a chunked/resumable hydration completion task
- keep the same canonical foundation target
- keep the same completed-season-to-date boundary
- do not promote the updater yet

---

## ACTIVE TASKS

| task_id | type | purpose |
|---------|------|---------|
| MLB_PITCHER_BULLPEN_HYDRATION_CHUNKED_BUILD_001 | code-writing task | Complete pitcher_game_logs and bullpen_context hydration using a chunked/resumable approach that can finish reliably and report trustworthy counts. |

---

## QUEUED TASKS

| task_id | type | status |
|---------|------|--------|
| MLB_DAILY_PREV_DAY_UPDATER_BUILD_001 | code-writing task | stays queued until pitcher/bullpen hydration completion is reviewed and accepted |
| CLEAN_RUNTIME_WINDOW_AUDIT_001 | read-only audit | deferred until post-restart n>=30 clean trades |

---

## Rebuild-track guidance
1. Keep the canonical storage/schema target unchanged
2. Complete pitcher and bullpen hydration with a chunk-safe path
3. Only then promote the daily updater
4. Do not move into model implementation until the data foundation is complete and accepted

---

## Explicit no-go items for now
- No broad repo sweep
- No speculative feature-engineering tasks
- No model implementation before the data foundation is complete
- No live-strategy tuning from contaminated history
- No updater activation before trustworthy pitcher/bullpen hydration counts exist
