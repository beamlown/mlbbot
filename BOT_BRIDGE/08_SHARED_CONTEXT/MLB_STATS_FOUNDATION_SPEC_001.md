# MLB_STATS_FOUNDATION_SPEC_001
## Canonical current-season MLB stats foundation spec
## Date: 2026-04-12

## Purpose
Define the canonical raw-data foundation for the MLB rebuild so backfill and daily ingestion can proceed without guessing.

This spec covers:
- storage location
- raw vs normalized separation
- required entities
- required vs optional fields
- file format and partitioning
- versioning and refresh rules
- season-to-date completeness definition
- safe/idempotent previous-day append rules

This is a paper-only / observation-mode rebuild artifact.
It does not authorize model implementation or live strategy changes.

---

## 1. Canonical storage layout

### Canonical root
`C:\Users\johnny\Desktop\mlb_model\data\foundation\mlb_statsapi\season=2026\`

### Required subtrees
- `raw\games\`
- `raw\teams\`
- `raw\team_game_logs\`
- `raw\pitcher_game_logs\`
- `raw\bullpen_context\`
- `raw\game_state_history\`
- `normalized\games\`
- `normalized\team_game_logs\`
- `normalized\pitcher_game_logs\`
- `normalized\game_state_features\`
- `manifests\`
- `metadata\`

### Separation rule
- `raw\` holds minimally transformed source-of-truth records from MLB Stats API.
- `normalized\` holds rebuild-ready standardized records derived only from `raw\`.
- No training-ready model tables should be written into `raw\`.
- No ad hoc one-off caches should be treated as canonical foundation data.

---

## 2. File format and partitioning

### File format
- Canonical file format: JSON Lines (`.jsonl`) for raw append-friendly entities.
- Normalized layer may use `.jsonl` or `.parquet` if later build tasks need columnar access, but raw must remain append-readable and debuggable.

### Partitioning rules
Partition by:
- `entity`
- `season`
- `game_date`

Examples:
- `raw\games\game_date=2026-04-11\games.jsonl`
- `raw\team_game_logs\game_date=2026-04-11\team_game_logs.jsonl`
- `raw\pitcher_game_logs\game_date=2026-04-11\pitcher_game_logs.jsonl`
- `raw\game_state_history\game_date=2026-04-11\game_state_history.jsonl`

### Manifest rules
Each completed load window must write a manifest under:
- `manifests\backfill_YYYYMMDD.json`
- `manifests\daily_YYYYMMDD.json`

Each manifest must record:
- load type (`backfill` or `daily_prev_day`)
- date window covered
- entities written
- record counts by entity
- source API name
- run timestamp
- checksum/hash of written files if available
- status (`success` / `partial` / `failed`)

---

## 3. Required entities

## Must-have entities
1. `games`
   - one record per completed MLB game
2. `teams`
   - canonical team identifiers / abbreviations / names
3. `team_game_logs`
   - one row per team per game
4. `pitcher_game_logs`
   - one row per pitcher appearance / game summary needed for rebuild
5. `bullpen_context`
   - bullpen-usage summary for each team/game if available from source derivation
6. `game_state_history`
   - inning / half / outs / score-state progression if available

## Optional but high-value entities
- batting-order context
- richer boxscore participant detail
- runner/base-state timeline richer than final summary snapshots
- leverage/index-like derived game-state context if easily derivable from raw state history

---

## 4. Required fields vs optional fields

### Required fields: games
- `game_pk`
- `game_date`
- `season`
- `status`
- `home_team_id`
- `away_team_id`
- `home_team_abbr`
- `away_team_abbr`
- `home_score`
- `away_score`
- `winner_team_id`
- `loser_team_id`
- `venue_id` if available
- `start_time_utc`
- `end_time_utc` if available

### Required fields: teams
- `team_id`
- `team_abbr`
- `team_name`
- `league`
- `division` if available

### Required fields: team_game_logs
- `game_pk`
- `game_date`
- `team_id`
- `opponent_team_id`
- `is_home`
- `runs_scored`
- `runs_allowed`
- `hits`
- `errors` if available
- `win_flag`
- `starting_pitcher_id` if available
- `bullpen_innings` if available
- `bullpen_runs_allowed` if available

### Required fields: pitcher_game_logs
- `game_pk`
- `game_date`
- `pitcher_id`
- `team_id`
- `is_starting_pitcher`
- `innings_pitched`
- `hits_allowed`
- `runs_allowed`
- `earned_runs`
- `walks`
- `strikeouts`
- `pitches_thrown` if available

### Required fields: bullpen_context
- `game_pk`
- `game_date`
- `team_id`
- `bullpen_pitchers_used`
- `bullpen_innings`
- `bullpen_runs_allowed`
- `bullpen_pitch_count` if available

### Required fields: game_state_history
- `game_pk`
- `game_date`
- `inning`
- `inning_half`
- `outs`
- `home_score`
- `away_score`
- `batting_team_id` if available
- `pitching_team_id` if available
- `base_state` if available
- `event_ts` or ordered sequence field

### Optional fields
Optional fields may be retained when available, but must not block first-pass backfill:
- advanced Statcast-like measures not directly available from the chosen source
- umpire/weather metadata
- full event narrative text
- batter-level pitch-by-pitch detail unless later required

---

## 5. Versioning and refresh rules

### Versioning
- Foundation dataset version: `v1`
- Store version metadata in `metadata\foundation_version.json`
- If schema changes later, create `v2` rules explicitly rather than silently mutating `v1`

### Refresh rules
- Backfill writes season-to-date completed games only.
- Daily updater writes previous-day completed games only.
- Same-day in-progress games must not be treated as final canonical completed-game records.
- If a source correction occurs, reruns may replace records for the affected `game_date`, but only through documented idempotent overwrite-by-partition rules.

---

## 6. Definition of complete season-to-date coverage

Season-to-date coverage is complete when:
- every completed MLB game from Opening Day of 2026 through the target coverage date exists in `raw\games\`
- every completed game has matching team_game_logs for both teams
- every completed game has pitcher_game_logs for all required pitcher summaries available from source
- bullpen_context exists for each completed game where derivable from source
- game_state_history exists for each completed game where available from source or the dataset explicitly records unavailable coverage in the manifest
- manifests show no missing game dates in the covered range

If any entity is unavailable from source for a given day/game, the manifest must explicitly record that as `source_unavailable`, not silently omit it.

---

## 7. Daily updater append/idempotency rules

The future daily updater must:
- fetch only the previous day’s completed MLB games
- write to the same canonical raw store and partition paths
- be idempotent by `game_pk` within each entity
- either upsert-by-primary-key or replace the full affected `game_date` partition atomically
- never append duplicate records for the same `game_pk` + entity
- write a manifest for every run
- fail loudly on partial entity writes rather than silently producing mixed partitions

### Safe append rule
Preferred rule:
- rebuild the full `game_date=YYYY-MM-DD` partition for the previous day in a temp path
- validate record counts
- atomically replace the target partition
- then write the manifest

This is safer than record-by-record append for daily stats ingestion.

---

## 8. Normalized layer rules

The normalized layer must be derived from raw only.
It should provide stable downstream shapes for rebuild/backtest work, including:
- standardized team IDs and abbreviations
- one-row-per-game canonical game table
n- one-row-per-team-per-game canonical team log table
- one-row-per-pitcher-per-game canonical pitcher log table
- one-row-per-game-state-step or summarized state-feature table where available

Normalized outputs must preserve:
- `game_pk`
- `game_date`
- `season`
- stable foreign keys to teams and pitchers

---

## 9. What this spec enables next
This spec enables:
1. `MLB_CURRENT_SEASON_BACKFILL_BUILD_001`
2. `MLB_DAILY_PREV_DAY_UPDATER_BUILD_001`

It does not yet authorize:
- feature-engineering work
- model retraining
- live model changes
- strategy tuning
