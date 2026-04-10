# DASHBOARD_REDESIGN_SPEC_001

## Task
DASHBOARD_REDESIGN_ARCH_001

## Scope
Architecture spec only. No production code changes.

## Current dashboard read summary
Current `dashboard.html` is a two-column MLB dashboard with:
- sticky command bar
- left-column live monitor / position cards
- right-column live games focus, games ticker, KPI strip, and drawer tabs
- current drawer tabs: `Trade Log`, `Shadow`, `Candidates`, `Manual`

Current `dashboard_server.py` exposes these main read paths:
- `/api/state`
- `/api/trades`
- `/api/games`
- `/api/markets`
- `/api/signals`
- `/api/candidates`
- `/api/mlb-shadow`
- `/api/bankroll`
- `/api/debug/market-stream`
- `/api/stream/state` (SSE `positions_mark`)

## Exact redesign tab contract
Default tab on load: `LIVE`

Exact tab list:
1. `LIVE`
2. `POSITIONS`
3. `GAMES`
4. `HISTORY`
5. `SYSTEM`

## Tab definitions

### 1. LIVE
Primary operator surface. This is the only default landing view.

Focal area order, top to bottom:
1. live game monitor
2. live position cards
3. account strip

LIVE shows:
- live game monitor for games tied to open positions first
- active position truth cards only
- compact account strip with bankroll / committed / open / r25 metrics

LIVE must not show:
- shadow/advisory feed
- trade history log
- candidate list
- manual trade entry controls
- deep diagnostics that compete with position truth

### 2. POSITIONS
Dedicated active and recent execution-position view.

POSITIONS shows:
- all open paper positions
- optionally most recent closed positions in a secondary section
- held-contract truth fields and team-direction display

POSITIONS must not show:
- shadow advisory as a competing truth source
- manual entry form
- candidate list as primary content

### 3. GAMES
Game-centric board for live and upcoming MLB games.

GAMES shows:
- all live and upcoming games
- game status, inning, score, outs, runners, pitchers if available
- model shadow recommendations only as clearly labeled secondary advisory context

GAMES must not show:
- shadow recs as execution truth
- trade log as primary content

Shadow policy here:
- label clearly as `Shadow Advisory — Not Executed`
- visually secondary to live game state
- never merged into active position cards

### 4. HISTORY
Trade history only.

HISTORY shows:
- trade log with team names
- side direction
- entry / exit / pnl / size
- close reasons when available

HISTORY must not show:
- shadow advisory feed
- live monitor as primary content

### 5. SYSTEM
Operational diagnostics only.

SYSTEM shows:
- stream health
- mark counts
- fallback status
- process topology / source chain summary
- bot loop stats
- debug status from `/api/debug/market-stream`
- stale / freshness diagnostics

SYSTEM must not show:
- manual trade entry as primary operator workflow
- shadow data mixed with execution truth

## LIVE tab layout contract

### A. Live game monitor
Highest visual priority.
Fields:
- `home_team`
- `away_team`
- `inning`
- `inning_half`
- `home_score`
- `away_score`
- `status`
- `outs`
- `balls`
- `strikes`
- `on_first`
- `on_second`
- `on_third`
- `home_pitcher` if available
- `away_pitcher` if available
- `active_position_flag`
- `model_confidence` if available, but secondary

### B. Live position cards
Second focal area.
Each card must represent execution truth, not advisory truth.

Position card required fields:
- `backed_team`
- `faded_team`
- `entry_px`
- `current_held_price`
- `unrealized_pct`
- `live_equity`
- `tp_price`
- `sl_price`
- `size_usd`
- `held_contract_side`
- `market_slug` only as secondary metadata, never primary label
- freshness / stale badge

Display semantics:
- use team direction like `LAD WIN` or `TOR LOSE`
- do not make raw `BUY_YES` / `BUY_NO` the primary human-facing label
- do not use raw slug as card title when team names are available

### C. Account strip
Third focal area, always visible on LIVE.
Required fields:
- `bankroll`
- `capital_committed`
- `open_count`
- `r25.win_rate`
- `r25.expectancy`

## Payload mapping table

| Frontend field | API source | Source field / derivation |
|---|---|---|
| bankroll | `/api/state` | `bankroll.current` |
| capital_committed | `/api/state` | `bankroll.capital_committed` |
| open_count | `/api/state` | `bankroll.open_trade_count` or open positions count |
| r25.win_rate | `/api/state` | `r25.win_rate` |
| r25.expectancy | `/api/state` | `r25.expectancy` |
| market loop / mode / bridge | `/api/state` | `loop_count`, `mode`, `bridge_enabled` |
| open positions base rows | `/api/trades` | rows where `status='open'` |
| entry_px | `/api/trades` | `entry_px` |
| qty | `/api/trades` | `qty` |
| tp_price | `/api/trades` | `tp_price` |
| sl_price | `/api/trades` | `sl_price` |
| current_held_price | SSE `/api/stream/state` | `positions[].current_price` |
| unrealized_pnl_usd | SSE `/api/stream/state` | `positions[].unrealized_pnl_usd` |
| live_equity | SSE `/api/stream/state` | `positions[].live_equity_usd` |
| best_bid | SSE `/api/stream/state` | `positions[].best_bid` |
| best_ask | SSE `/api/stream/state` | `positions[].best_ask` |
| spread | SSE `/api/stream/state` | `positions[].spread` |
| price freshness / stale | SSE `/api/stream/state` | `positions[].current_price_stale`, `source_ts`, `mark_source` |
| game_status / inning / score on position cards | SSE `/api/stream/state` | `positions[].game_status`, `inning`, `inning_half`, `outs`, `home_score`, `away_score` |
| live games board | `/api/games` | `games[]` |
| all market reference rows | `/api/markets` | `markets[]` |
| history rows | `/api/trades` | closed trades |
| candidates diagnostics | `/api/candidates` | `candidates[]`, `thresholds` |
| shadow advisory | `/api/mlb-shadow` | `recs[]`, `pnl` |
| system stream diagnostics | `/api/debug/market-stream` | full payload |

## Truth-model preservation checklist

| Constraint | Requirement | Pass/Fail for redesign contract |
|---|---|---|
| current_price_authority | stream-backed held-side bid only | PASS |
| fallback_policy | fallback only when stream missing/stale, labeled | PASS |
| shadow_policy | shadow not on LIVE or POSITIONS as competing truth | PASS |
| backed_team_semantics | display backed/faded team direction, not raw contract economics | PASS |
| no_new_price_writers | keep single authority chain `polymarket stream -> state_hub -> SSE -> frontend` | PASS |

## Frontend / backend split

### Computed server-side
Should remain server-side:
- current held price from state hub / stream
- unrealized PnL dollars
- live equity dollars
- freshness / stale fields
- trade TP / SL fields
- bankroll / r25 metrics
- stream diagnostics

### Computed client-side
Allowed client-side only for presentation:
- sorting / grouping cards by live/open status
- tab visibility
- compact formatting (`¢`, `$`, `%`, age labels)
- deriving `unrealized_pct` from trusted server fields when not directly provided
- deriving human labels like `LAD WIN` from trusted team / direction fields

### Required backend additions
Minimal only, if not already present in payloads:
- `backed_team`
- `faded_team`
- `held_contract_side`
- `current_held_price` as explicit alias/name for current held-side mark
- optional `active_position_flag` on game monitor rows

No new price-writing path is allowed.

## Demotion list
These items are currently above the fold or too prominent and must be removed or demoted from LIVE:
- shadow feed panel
- trade log panel
- candidates panel
- manual trade entry form
- guard stack as primary content
- open positions debug cards that duplicate live position truth
- diagnostics competing with active positions

Destination after demotion:
- shadow -> `GAMES` only, clearly labeled advisory
- trade log -> `HISTORY`
- candidates -> `SYSTEM` or secondary diagnostics section
- manual trade entry -> `SYSTEM` only if retained at all
- guard stack -> `SYSTEM`

## Current above-the-fold dominance assessment
Current mobile and desktop emphasis is mixed and not yet aligned to the redesign target because:
- live monitor and live games are split across columns
- shadow feed remains a first-class drawer tab
- trade log and manual controls are co-located in the same details region
- tab names do not match the final 5-tab contract

## File read findings relevant to redesign

### dashboard.html currently contains
- command bar / KPI strip / games ticker
- left-column live position monitor
- right-column live games focus
- drawer tabs: Trade Log / Shadow / Candidates / Manual
- client merges `/api/trades`, `/api/mlb-shadow`, `/api/games`, `/api/state`, and SSE positions marks
- current client still computes some card semantics and labels locally

### dashboard_server.py currently contains
- state reader and bankroll/r25 enrichments
- trades fetch with TP/SL derivation
- ESPN game polling cache
- shadow log reader
- SSE positions stream based on `GLOBAL_STATE_HUB.snapshot()`
- tracked asset resolution via discovery cache

## Explicit truth statements for later phases
- `current_held_price` must mean the held-side contract mark only.
- For BUY_YES positions, `current_held_price = bid_yes`.
- For BUY_NO positions, `current_held_price = bid_no`.
- Display layer must never reinterpret BUY_NO using raw YES price.
- Shadow advisory must never override or appear equal to execution truth.
- backed_team semantics must remain consistent from execution through SSE to UI labels.

## Five-tab layout summary
- `LIVE`: live game monitor, live position cards, account strip
- `POSITIONS`: full open/recent position management view
- `GAMES`: all games plus clearly segregated shadow advisory
- `HISTORY`: trade log only
- `SYSTEM`: diagnostics, stream health, thresholds, topology

## Acceptance notes for later phases
All subsequent redesign phases must be reviewed against this contract:
- exact tab names must match
- default tab must be LIVE
- shadow must be absent from LIVE and POSITIONS
- current_held_price authority must remain SSE held-side mark
- no new pricing authority may be introduced

## Proof of work
Output file:
- `C:\Users\johnny\Desktop\BOT_BRIDGE\08_SHARED_CONTEXT\DASHBOARD_REDESIGN_SPEC_001.md`

Production file changes:
- none
