# MLB Model — Operator Runbook (Phase-1)

## Daily ops

Run these every morning (cron-able). Both must run from the `mlb_model/` directory:

```bash
cd C:/Users/johnny/Desktop/mlb_model

# 1. Roll yesterday's MLB results into elo_table.parquet
python scripts/update_elo_daily.py

# 2. Snapshot today's Pinnacle moneylines (requires ODDS_API_KEY)
python scripts/update_sharp_odds_daily.py
```

Both write to `data/features/`. Stale parquets (>36h for Elo, >24h for sharp odds) trip the startup self-check:

- **Stale Elo (>36h)** → HALT. Bot refuses to trade. Run the updater.
- **Stale sharp (>24h)** → NO_NEW_ENTRIES (soft warning). Set `ALLOW_STALE_SHARP=1` to suppress and run Elo-only.

## Initial bootstrap

First-time setup (one-shot, slow — pulls historical data):

```bash
cd C:/Users/johnny/Desktop/mlb_model

# 1. Park factors (uses local retrosheet parquets in data/raw/retrosheet/)
python -m data.foundation.park_factor_builder

# 2. Pitcher quality (network: pulls 2018-2025 from pybaseball, ~30 min)
python -m data.foundation.pitcher_quality_builder

# 3. Sharp odds: backfill not available from the-odds-api free tier.
#    The first snapshot creates the parquet; live model will fall back to Elo
#    for any historical games without a sharp row (this is by design — see
#    pregame_prior_source flag in feature schema).
python scripts/update_sharp_odds_daily.py

# 4. Retrain (full pipeline, audit-gated promotion)
python scripts/retrain_after_features.py
```

## Promotion outcomes

`scripts/retrain_after_features.py` produces `artifacts/audit_report.json` and exits with one of:

| Exit | Verdict | Action |
|---|---|---|
| `0` | `PROMOTE` | New artifacts deployed; old archived to `artifacts/archive/<ts>/` |
| `2` | `PROMOTE_WITH_CAVEAT` | Manual review required (passes shap or lift but fails ablation, or vice versa) |
| `1` | `REJECT` | Old artifacts kept; check `audit_report.json` for which gate failed |

## Rollback

Promoted a bad model and want to revert?

```bash
cd C:/Users/johnny/Desktop/mlb_model

# 1. Find archive timestamp
ls artifacts/archive/

# 2. Copy back
cp artifacts/archive/<TS>/* artifacts/

# 3. Restart shadow loop
python -m integration.recommendation_api
```

## Environment variables

| Var | Purpose | Default |
|---|---|---|
| `ODDS_API_KEY` | the-odds-api.com Pinnacle tier key | (required for sharp odds) |
| `ALLOW_STALE_SHARP` | `1` to suppress stale-sharp soft-warn (Elo-only mode) | unset |
| `PHASE` | `shadow` / `advisory` / `merged` | `shadow` |
| `MIN_EDGE_THRESHOLD` | Min edge for actionable recommendation | `0.05` |
| `STRONG_EDGE_THRESHOLD` | Edge above which size_tier=strong | `0.08` |
| `FEATURE_DIR` | Override path to features parquets | `data/features` |
| `ARTIFACT_DIR` | Override path to model artifacts | `artifacts` |
| `GAME_STATE_MAX_AGE_SEC` | Max age for live game state | `15` |
| `BOOK_MAX_AGE_SEC` | Max age for order book snapshot | `5` |

## Self-check on startup

The bot's `core.selfcheck.startup_check()` runs these checks (extended in Phase-1):

**Hard (HALT on fail):**
- ESPN scoreboard reachable
- Live game detection works
- Model artifacts loaded
- Phase config set
- `feature_schema.json` reports `n_features == 30` (mismatch = stale model, won't trade)
- `elo_table.parquet` < 36h old

**Soft (NO_NEW_ENTRIES on fail):**
- Elo table loaded
- `sharp_odds_history.parquet` < 24h old (suppressible via `ALLOW_STALE_SHARP=1`)
- Gamma API reachable

## Windows Task Scheduler installation (#1.5)

Three daily scheduled tasks are wired up via `scripts/cron/`:

| Task name | Time (CT) | Wrapper |
|---|---|---|
| `mlb-elo-daily` | 06:00 | `run_update_elo_daily.bat` |
| `mlb-pitcher-quality-daily` | 08:00 | `run_refresh_pitcher_quality_daily.bat` |
| `mlb-sharp-odds-daily` | 09:00 | `run_update_sharp_odds_daily.bat` |

### Install (one-time)

Double-click `scripts/cron/install_scheduled_tasks.bat`, OR open Command Prompt and run:

```cmd
C:\Users\johnny\Desktop\mlb_model\scripts\cron\install_scheduled_tasks.bat
```

Re-runnable; uses `/F` to overwrite if already installed.

### Verify

```cmd
schtasks /Query /TN mlb-elo-daily
schtasks /Query /TN mlb-pitcher-quality-daily
schtasks /Query /TN mlb-sharp-odds-daily
```

### Run on demand

```cmd
schtasks /Run /TN mlb-elo-daily
```

### Logs

All three append stdout/stderr to `logs/cron.log`.

### Uninstall

```cmd
schtasks /Delete /TN mlb-elo-daily /F
schtasks /Delete /TN mlb-pitcher-quality-daily /F
schtasks /Delete /TN mlb-sharp-odds-daily /F
```

## Known operational notes

- **ESPN team abbreviations** (used by `elo_daily_updater.py`) must match the abbreviations already in `elo_table.parquet`. If ESPN renames a franchise (e.g., OAK → ATH), unknown abbreviations get default rating 1500 instead of inheriting prior history. Spot-check the first run after roster moves.
- **Park IDs** in `park_factors.parquet` must match what `snap.venue_id` reports from the live game state service. If retrosheet uses one ID scheme and ESPN another, the live lookup falls back to neutral 1.0 (see `sports/mlb/park_factor_live.py`).
- **Pitcher IDs**: `pitcher_quality.parquet` keys on the names from pybaseball; `snap.home_pitcher_id` is currently an ESPN numeric ID. There may be a join mismatch on first run — the live lookup will impute league-mean (sp_quality=100) and set `home_sp_imputed=True`. Resolve by either (a) building a name↔id mapping, or (b) updating the builder to key on MLB IDs.
- **Phase-1 features in offline training**: historical snapshots may not include `home_pitcher_id`/`park_id` columns. The feature_store's enrichment fills neutral defaults in that case, and the audit step will detect zero signal and REJECT — which is correct behavior. Live inference uses the live lookups directly and is unaffected.
