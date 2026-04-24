STATUS: COMPLETE — filetree drift resolved per AUDIT_FILETREE_DRIFT_2026-04-18

# Remediation — filetree drift (operator action, 2026-04-18)

Executed by operator in response to `AUDIT_FILETREE_DRIFT_2026-04-18.md` BLOCK. All remediation items 1–6 are done. Items 7 (revise restart HANDOFF) and 8 (re-run RESTART_CONFIG_HASH_VERIFY) are left for the next patch cycle per the audit order.

## Canonical tree (locked)

- `C:\Users\johnny\Desktop\sports_bot_v2\` — canonical source, receives all patches, runs the live paper bot.
- `C:\Users\johnny\Desktop\mlbbot\BOT_BRIDGE\` — canonical bridge queue (05/06/07/08 + newly-added 01_RULES).

## Actions taken

### 1. Orphan processes killed

Pre-remediation inventory showed 5 live PIDs rooted at `mlbbot\sports_bot_v2\` (the stale 2026-04-17 09:19 clone):

| PID   | Role                          | Parent | Source tree        | Action |
|-------|-------------------------------|--------|--------------------|--------|
| 37164 | `bot_core.py`                 | 4636   | mlbbot (orphan)    | killed |
| 4636  | `launch_all.py`               | —      | mlbbot (orphan)    | killed |
| 14164 | `integration.recommendation_api` | 4636 | mlbbot (orphan)    | killed |
| 21336 | `dashboard_server.py`         | 4636   | mlbbot (orphan)    | killed |
| 3248  | `integration.resolution_watcher` | 4636 | mlbbot (orphan)    | killed |

Pre-kill check confirmed orphan `bot_core.py` had `open_positions: []` and `slots.open: 0` — no in-flight trade exposure. `mlbbot/.../runtime/bot.pid` held 37164; `launcher.pid` held 4636 — matches.

Post-kill python inventory: all surviving PIDs either child-of-18680 (Desktop launcher tree) or standalone Desktop dashboards / control_plane. No mlbbot rooted python processes remain.

### 2. Orphan tree quarantined

Renamed to block accidental re-launch:

- `C:\Users\johnny\Desktop\mlbbot\sports_bot_v2\` → `C:\Users\johnny\Desktop\mlbbot\sports_bot_v2.ORPHAN_ARCHIVE_2026-04-18\`

Kept (not deleted) so forensics can diff against canonical if any regression shows up. Safe to delete after one full audit cycle confirms the canonical tree is the sole source of truth.

### 3. 01_RULES migrated to canonical bridge

Copied verbatim from `Desktop\BOT_BRIDGE\01_RULES\` to `mlbbot\BOT_BRIDGE\01_RULES\`:

- `BOT_BRIDGE_OPERATING_PRINCIPLES.md`
- `MANAGER_RULES.md`
- `REVIEW_RULES.md`
- `WORKER_RULES.md`

Doctrine now lives at the active bridge. Old copies remain at `Desktop\BOT_BRIDGE\01_RULES\` until role configs are fully repointed away from that path (current `.claude-roles/*/CLAUDE.md` already reference `mlbbot\BOT_BRIDGE\`).

### 4. Debris purged from `Desktop\BOT_BRIDGE\` root

Moved to `Desktop\BOT_BRIDGE\09_ARCHIVE\debris_2026-04-18\`:

- `_tmp_late_inning_packet/` (dir)
- `_tmp_mlb_backfill.py`, `_tmp_mlb_backfill_fix.py`, `_tmp_mlb_boundary_fix.py`, `_tmp_pitcher_bullpen_build.py`, `_tmp_pitcher_bullpen_chunked.py`
- `incident_db_remediation_001.py`, `incident_db_verify_001_readonly.py`
- `proof_execution_metadata_persistence_001.py`, `proof_execution_metadata_persistence_001_output.json`
- `proof_verify_odds_budget_001.py`, `proof_verify_odds_budget_001_output.json`
- `temp_execution_metadata_proof.db`, `temp_odds_budget_verify.json`
- `export_botbridge_review.ps1`

`Desktop\BOT_BRIDGE\` root now shows only the 11 canonical 00–10 subfolders.

### 5. Nested stub removed

Deleted `Desktop\sports_bot_v2\BOT_BRIDGE\08_SHARED_CONTEXT\BANKROLL_ACCOUNTING_SPEC_001.md` after confirming `mlbbot\BOT_BRIDGE\08_SHARED_CONTEXT\BANKROLL_ACCOUNTING_SPEC_001.md` exists. Removed the now-empty `Desktop\sports_bot_v2\BOT_BRIDGE\` tree as well.

### 6. Canonical bot verified healthy post-remediation

- PID 37184 `bot_core.py` still alive, parent 18680 (Desktop launcher).
- `Desktop\sports_bot_v2\runtime\state.json`: `config_hash=f87077f219dd`, `loop_count` advanced 245 → 247 during remediation, `open_positions=[]`, no guard faults.

## Left for next cycle (items 7 & 8 from audit)

- Revise DRAFT_HANDOFF for restart to enumerate all PIDs, abort if >1 `bot_core.py` is seen, and assert single canonical cwd.
- Re-run `RESTART_CONFIG_HASH_VERIFY` against the canonical tree only.

## Ship gate

Drift BLOCK cleared. The system can now be audited coherently — exactly one `bot_core.py` running, on the canonical tree, under the expected config hash.
