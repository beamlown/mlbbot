DECISION: BLOCK

# AUDIT — filetree/codebase drift across Desktop vs mlbbot (2026-04-18)

## TL;DR

**Two bots are running in parallel right now, on different source trees, with different config hashes, both writing paper trades.** The `mlbbot/sports_bot_v2/` tree is an orphan clone from 2026-04-17 09:19 that never received any patches — it has its own `state.json` (hash `73a56b988927`), its own `bot_core.py` (MD5 `47383d11`), its own `logs/`, and its own `trades_sports.db` — yet it is live and looping. The "real" bot lives at `C:\Users\johnny\Desktop\sports_bot_v2\` (hash `f87077f219dd`, MD5 `3f622bb7`). The RESTART_CONFIG_HASH_VERIFY_001 audit I approved yesterday only verified the Desktop tree; it was blind to the parallel mlbbot bot.

The BOT_BRIDGE queue (05/06/07/08) has successfully migrated to `mlbbot\BOT_BRIDGE\` — that half of the drift is resolved by design. The source code / runtime half is NOT resolved and is actively diverging.

Recommend BLOCK on the next ship. Kill the orphan bot and reconcile paths before any further patches are audited.

---

## What I found

### 1. Two live `bot_core.py` processes, two trees

`wmic` / `Get-CimInstance` confirms two simultaneous PIDs both running `bot_core.py`:

| PID | cwd (implied by state.json writes) | config_hash | source MD5 |
|-----|------------------------------------|-------------|------------|
| 37184 | `C:\Users\johnny\Desktop\sports_bot_v2\` | `f87077f219dd` | `3f622bb76d91e6660f3bc77307d5eb6d` |
| 37164 | `C:\Users\johnny\Desktop\mlbbot\sports_bot_v2\` | `73a56b988927` | `47383d115a49db52c26798d59c39edbc` |

Both `runtime/state.json` files were last written at 2026-04-18 00:51 (same minute). Both `logs/bot_baseball_20260418.log` files are actively appending (2026-04-18 00:52). Each tree has its own `trades_sports.db`. Each has its own `runtime/bot.pid`, each pointing to a different PID.

This is not a stale-snapshot-sitting-on-disk situation. It is two live trading processes.

### 2. All four compared source files diverge between trees

MD5 comparison (Desktop ←→ mlbbot):
- `bot_core.py`: `3f622bb7...` ≠ `47383d11...`
- `dashboard_server.py`: `918f1b7c...` ≠ `4cc98ba4...`
- `core/model_bridge.py`: `465ff337...` ≠ `a88a7e68...`
- `core/risk.py`: `e28ec8c8...` ≠ `47a090f7...`

mtime pattern on `core/*.py`:
- `Desktop/sports_bot_v2/core/`: varied mtimes from 2026-04-01 through 2026-04-17 17:57 (live, edited over time)
- `mlbbot/sports_bot_v2/core/`: **every file is 2026-04-17 09:19** (wholesale copy; never edited since)

Conclusion: `mlbbot/sports_bot_v2/` was a one-time copy taken 2026-04-17 ~09:19 and has received zero worker edits since. All subsequent patches (BOT_DATE_GATE, LATE_INNING_BLOCK wiring, CONFIG_HASH changes, etc.) landed only on the Desktop tree.

### 3. Role configs confirm the split is effectively by design for BOT_BRIDGE but accidental for source

`.claude-roles/*/CLAUDE.md` path references:

- **worker/CLAUDE.md**: reads HANDOFFs from `mlbbot\BOT_BRIDGE\05_INBOX_FROM_MANAGER\`, writes RESULTs to `mlbbot\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\`, but edits code at `C:\Users\johnny\Desktop\sports_bot_v2\` (old path).
- **reviewer/CLAUDE.md**: operates entirely under `mlbbot\BOT_BRIDGE\`.
- **auditor/CLAUDE.md** (this role): operates entirely under `mlbbot\BOT_BRIDGE\`.
- **manager**: no CLAUDE.md in `.claude-roles/`.

So the Bridge queue IS unified at `mlbbot\BOT_BRIDGE\` (corroborated by timestamps: old Desktop `07_REVIEWS` newest = 2026-04-12; mlbbot `07_REVIEWS` newest = 2026-04-18 00:07). The SOURCE code path in worker config correctly points to the Desktop tree — which means `mlbbot/sports_bot_v2/` is not being written to by any HANDOFF-driven worker. It's just sitting there, running, reading its own stale files.

### 4. Previous reviewer notes about "old path" were misreading their own environment

Several recent REVIEWs (e.g. RESTART_CONFIG_HASH_VERIFY_001, RULES_DOCTRINE_UPDATE_001) flagged the worker for "reading from old `C:\Users\johnny\Desktop\BOT_BRIDGE\` path rather than `mlbbot\BOT_BRIDGE\`." Spot-check of both BOT_BRIDGE trees shows:

| Folder | Desktop/BOT_BRIDGE newest | mlbbot/BOT_BRIDGE newest |
|--------|----------------------------|--------------------------|
| 05_INBOX | 2026-04-17 17:02 | 2026-04-18 00:47 |
| 06_OUTBOX | 2026-04-17 16:16 | 2026-04-18 00:48 |
| 07_REVIEWS | 2026-04-12 12:00 | 2026-04-18 00:07 |
| 08_SHARED_CONTEXT | ~60 files (stale) | 197 files (current) |

Workers ARE using `mlbbot\BOT_BRIDGE\` for the active queue. The reviewer confusion was spurious — the paths both exist and the old one has some stragglers (Apr 17 17:02 HANDOFF, Apr 17 16:16 RESULT) but the active flow is on mlbbot.

The real drift is not BOT_BRIDGE paths. It is the parallel `sports_bot_v2/` tree.

### 5. `01_RULES` lives only at the old Desktop path

`mlbbot\BOT_BRIDGE\` has subfolders 05/06/07/08 only. `Desktop\BOT_BRIDGE\` has 00_START_HERE, 01_RULES, 02_PROMPTS, 03_TEMPLATES, 04_QUEUE, 09_ARCHIVE, 10_LOGS — none of these were migrated. So the doctrine file `BOT_BRIDGE_OPERATING_PRINCIPLES.md` approved in RULES_DOCTRINE_UPDATE_001 lives only at the old path. Any role whose CLAUDE.md references `mlbbot\BOT_BRIDGE\01_RULES\...` will fail to find it. (None currently do — I grep-checked — but README pointers in the old path may silently mislead.)

### 6. Loose tmp files in old Desktop/BOT_BRIDGE root

`_tmp_late_inning_packet`, `_tmp_mlb_backfill.py`, `_tmp_mlb_backfill_fix.py`, `_tmp_mlb_boundary_fix.py`, `_tmp_pitcher_bullpen_build.py`, `_tmp_pitcher_bullpen_chunked.py`, `incident_db_remediation_001.py`, `incident_db_verify_001_readonly.py`, `proof_execution_metadata_persistence_001.py`, `proof_execution_metadata_persistence_001_output.json`, `proof_verify_odds_budget_001.py`, `proof_verify_odds_budget_001_output.json`, `temp_execution_metadata_proof.db`, `temp_odds_budget_verify.json`, plus a PowerShell export script. These were dropped at the Bridge root by prior workers in violation of workspace hygiene. Non-urgent but worth purging.

### 7. Nested stub at `Desktop\sports_bot_v2\BOT_BRIDGE\08_SHARED_CONTEXT\`

Contains one file: `BANKROLL_ACCOUNTING_SPEC_001.md`. Looks like an accidental write by a worker whose cwd was the bot source dir. Should be moved to the canonical shared context or deleted.

---

## Why this matters for shipping

1. **My last audit was blind to half the runtime.** AUDIT_2026-04-18-v1 confirmed `config_hash=f87077f219dd` at `Desktop/sports_bot_v2/runtime/state.json` and declared SHIP. I did not check `mlbbot/sports_bot_v2/runtime/state.json`, which shows `73a56b988927` — a hash the patch never intended to create because that bot never received the patch. The SHIP decision is technically correct for the Desktop bot, but the system as a whole is not in the state the audit implied.

2. **Two bots trading the same markets in paper mode** will either:
   - Write to different databases (the case today — two separate `trades_sports.db` files) → bankroll / PnL reports are split across two stores and whichever the operator looks at is half the truth.
   - Or, if pointed at the same Polymarket API with the same credentials, race for entries and step on each other's exits.

3. **Gate values can diverge silently.** The Desktop tree has `MIN_ENTRY_CONFIDENCE=0.65`. The mlbbot tree is running stale source — if any of these env vars were changed in the Desktop tree only (via a `.env` or hardcoded default), the mlbbot bot is making decisions under old rules. A confidence-calibration regression on the orphan bot would not show up in the log the operator monitors.

4. **Restart procedures are ambiguous.** The DRAFT_HANDOFF I filed for 2026-04-18-v1 restart assumed one canonical launcher and one PID. That is false today. A worker following it would restart one tree and leave the other alive — exactly the state we are already in.

---

## Recommended remediation (in order)

1. **Immediately stop `bot_core.py` PID 37164 (mlbbot tree).** It is running stale code under a hash the operator did not ship. Graceful shutdown preferred; `taskkill /PID 37164` after confirming no in-flight trade close.
2. Also stop `launch_all.py` processes rooted at `mlbbot/sports_bot_v2/` (PID 4636 explicitly, plus whichever of PIDs 12624 / 18680 is rooted there — check their cwd via `Get-CimInstance Win32_Process | Select ProcessId, ExecutablePath, @{n='CWD';e={$_.CommandLine}}`).
3. **Decide the canonical source tree.** Two viable paths forward:
   - **Option A (lowest risk):** Keep `C:\Users\johnny\Desktop\sports_bot_v2\` as canonical (it is the tree currently receiving patches and running the bot the audits have been tracking). Delete or archive `mlbbot\sports_bot_v2\` to prevent future accidental launches.
   - **Option B (clean but riskier):** Migrate the Desktop tree into `mlbbot\sports_bot_v2\` (overwriting the stale clone), update `worker/CLAUDE.md` to edit at the mlbbot path, then kill the old tree's launcher. Do not do this during live hours; requires its own patch cycle and audit.
4. **Migrate `01_RULES\` into `mlbbot\BOT_BRIDGE\` or formally bless the Desktop path.** One BOT_BRIDGE, one set of rules. Today the Bridge is effectively at mlbbot but rules are at Desktop.
5. **Purge `_tmp_*` / `incident_*` / `proof_*` / `temp_*` files from `Desktop\BOT_BRIDGE\` root.** Move to `09_ARCHIVE\` or delete.
6. **Delete the nested stub `Desktop\sports_bot_v2\BOT_BRIDGE\08_SHARED_CONTEXT\BANKROLL_ACCOUNTING_SPEC_001.md`** after confirming the real copy exists in the canonical shared context.
7. **Revise the DRAFT_HANDOFF for 2026-04-18-v1 restart** to explicitly enumerate ALL PIDs, not just the expected single one, and to abort if more than one `bot_core.py` is found before/after restart. Add a precondition: `(cwd of every live bot_core.py) == <single canonical path>`.
8. **Re-run RESTART_CONFIG_HASH_VERIFY** against the canonical tree only, after (1)–(3).

---

## Ship gate

Do not SHIP any further patch until items 1, 2, 3, and 7 are complete and verified. The system cannot be audited coherently while two bots are trading out of divergent trees.

DECISION: BLOCK pending remediation.
