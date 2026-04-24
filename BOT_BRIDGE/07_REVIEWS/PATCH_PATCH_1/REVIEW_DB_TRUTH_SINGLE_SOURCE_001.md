# REVIEW — DB_TRUTH_SINGLE_SOURCE_001

Scope: read-only audit of `sports_bot_v2/dashboard_server.py` to confirm
trades_sports.db is the single source of truth for historical/trade data,
and that per-endpoint sources are either DB or a documented exception.

## Verification performed

1. `grep paper_trades` across `sports_bot_v2/` (py + html): **0 matches**.
   Confirms `paper_trades_db_still_read: false` in the result JSON.
2. `DB_PATH = os.getenv("DB_PATH", "trades_sports.db")` at line 52; every
   `_db()` context manager (lines 213–220) connects to that path. All DB
   reads funnel through this single helper — no stray `sqlite3.connect`
   calls, no parallel DBs.
3. `/api/signals` handler (line 1084 → `_build_signals` at 889) now reads
   from `_fetch_trades(limit=100)` and filters `status=='open'`. The prior
   `state.open_positions` read is gone — `grep open_positions` returns only
   the output dict key at line 879, not a read.
4. `_refresh_game_state_hub` (372–394) now reads `_espn_scoreboard` under
   `_espn_lock` and calls `_fetch_trades()` — no `_read_games()` call
   remains (`grep _read_games` → 0 matches). Undefined-function bug fixed
   as claimed.
5. Cross-checked each endpoint in the inventory table against `do_GET`
   routing (1065–1146). All 15 endpoints map correctly:
   - Historical/trade endpoints (`/api/state`, `/api/trades`, `/api/signals`,
     `/api/attribution/*`, `/api/bankroll`, `/api/manual-trade`,
     `/api/mlb-shadow`) read trades_sports.db or an explicit log file
     (mlb-shadow JSONL is read-only audit data, acceptable).
   - Operational endpoints (`/api/games`, `/api/debug/market-stream`,
     `/api/stream/state`) correctly sourced from live caches; documented
     as exceptions with sound reasoning (live state ≠ trade history).
6. `/api/bankroll` computes lifetime net PnL via a direct `SUM(pnl_usd)`
   query (1117–1124), avoiding the 30-day cap on `_daily_pnl_history`.
   Comment at 1115–1116 explains the rationale.
7. `_read_state` uses `runtime/state.json` for operational state but
   cross-checks bankroll/session PnL against trades_sports.db (532–537).
   This is the correct V4-safe pattern — no silent fallback to a proxy.

## Handoff acceptance

- Full endpoint inventory provided (15 endpoints, handler file:line,
  data source, violation class). ✓
- Diffs for V4 signals fix and `_read_games` bug described with line
  anchors (888–904, 372–393). Code on disk matches. ✓
- Result JSON written to the declared outbox path with all required
  fields. ✓
- Scope guardrail honored: no new panels added; bot_core.py not
  modified; no paper_trades.db deletion. ✓

## Drift vs. prior TL;DRs

Step 1 flagged a blocking JS syntax error in `dashboard_v2.html`
(`lowSample?\\...`). This task does **not** touch `dashboard_v2.html`
or `dashboard.html` (confirmed by `files_changed` only listing
`dashboard_server.py`), so Step 1's block does not propagate into this
task. The Step 1 issue remains outstanding for its own task, but it is
orthogonal to this audit's deliverable.

## Minor observations (non-blocking)

- `/api/candidates` reads from `logs/audit_candidates_{SPORT}.jsonl`.
  Classified as clean because the file is a model-candidate audit log,
  not a DB-substituted trade metric. Reasonable, though a future task
  may want to state this exception explicitly rather than listing it
  under `clean_endpoints`.
- `_read_markets()` pulls from `runtime/last_discovery.json`. Same
  category — operational discovery cache, not trade history. Consider
  promoting this to `documented_exceptions` for consistency.

These are organizational nits, not violations; the sources are correct
for their purposes.

DECISION: APPROVED

TL;DR:
- paper_trades.db has zero references in dashboard code — single source of truth confirmed
- V4 signals endpoint and undefined `_read_games` bug both fixed on disk at claimed line ranges
- 15-endpoint inventory matches routing in do_GET; exceptions correctly limited to live operational state
- No drift from Step 1 — this task does not touch the dashboard HTML where the JS parse bug lives
- Minor suggestion: move `/api/candidates` and `/api/markets` JSONL sources into documented_exceptions for clarity
