# Dugout Dash — Port 8900 Redesign

**Date:** 2026-04-18
**Status:** Design (approved in brainstorming session)
**Supersedes:** `sports_bot_v2/dashboard_server.py` (single-page stdlib HTTP server)

---

## Summary

Replace the single-page `dashboard_server.py` on port 8900 with a Flask app, `dugout_dash`, that adopts the "DUGOUT OS" 8-bit baseball aesthetic already shipped in `mlbbot/control_plane` (port 8787). The new dashboard has five pages — `GAME`, `TRADES`, `TAPE`, `SYSTEM`, `HALL OF FAME` — a tazz.tv live stream embed with deep-link fallback, realtime trade notifications (in-page toast + OS notification + 8-bit sound cue), and live P&L updates driven by an in-process event bus over Server-Sent Events.

Nothing on the bot side changes except a single `event_bus.publish(...)` call inside `paper_fill` / `close_position` and the existing market stream tap.

---

## Goals

1. **Realtime contract first.** Trade entries and price ticks reach the browser in under 500 ms, end-to-end, with no page reload. P&L cells pulse on every tick and settle to green/red based on position direction.
2. **Aesthetic parity with control plane.** Scoreboard header, pixel fonts, amber LED chips, `[ NAV ]` bracket tabs, led-ribbon footer, `⚾ STEP UP` CTA — same design tokens, same fonts.
3. **Page-per-concern.** Each page has one job, lives in its own blueprint, and stays under ~250 lines. Shared chrome lives in `base.html`.
4. **Trade-joy.** Live notifications and the Hall of Fame make the bot feel like a game you're winning (or losing) at, not a console spewing JSON.

## Non-goals

- No auth, no multi-user, no remote access — still a single-operator local tool.
- No historical backtesting UI (that lives in mlb_model).
- No bot configuration editing from the UI (settings stay in `.env`).
- No mobile / responsive layout beyond "doesn't explode" — desktop only.
- No attempt to stream tazz.tv video through the bot's process. We embed if tazz allows iframes; otherwise deep-link.

---

## Architecture

### New package

```
sports_bot_v2/
└── dugout_dash/
    ├── __init__.py           # create_app() factory
    ├── config.py             # PORT=8900, DB_PATH, TAZZ_BASE_URL, bankroll, polling thresholds
    ├── events.py             # EventBus singleton — in-process pub/sub
    ├── market_tap.py         # subscribes to GLOBAL_MARKET_STREAM, republishes to EventBus
    ├── blueprints/
    │   ├── game.py           # /  and  /game/<espn_id>
    │   ├── trades.py         # /trades
    │   ├── tape.py           # /tape
    │   ├── system.py         # /system + pause/resume/flat controls
    │   ├── hof.py            # /hof
    │   └── api.py            # /api/events (SSE), /api/trades.json, /api/tape.json, /api/games.json
    ├── hof_sql.py            # SQL views / queries for Hall of Fame stats
    ├── templates/
    │   ├── base.html                # scoreboard header, nav, footer, toast/notify/SSE JS
    │   ├── partials/
    │   │   ├── game_tile.html       # sidebar mini-scoreboard
    │   │   ├── trade_row.html       # one row — reused on GAME detail + TRADES + notifications
    │   │   ├── ticker_cell.html     # marquee cell (TAPE strip)
    │   │   └── pos_card.html        # position card with P&L + gates + shadow rec
    │   ├── game.html
    │   ├── trades.html
    │   ├── tape.html
    │   ├── system.html
    │   └── hof.html
    └── static/
        ├── app.css            # pixel section lifted from control_plane/app.css + dash-only additions
        ├── dugout.js          # toast, Notification API, SSE client, sound player, P&L recompute
        ├── sounds/
        │   ├── base_hit.wav   # trade_entered
        │   ├── strikeout.wav  # stop_loss exit
        │   ├── walkoff.wav    # take_profit exit
        │   └── foul.wav       # SSE reconnect / stale
        └── sprites/           # batter.png, ball.png, diamond.png, trophy.png — image-rendering: pixelated
```

### Data sources (all existing — no new I/O added)

| Source | Used by | Notes |
|---|---|---|
| `core.market_stream.GLOBAL_MARKET_STREAM` | TAPE, TRADES, GAME P&L | Already running WebSocket to CLOB. `market_tap.py` subscribes once, publishes `mark_update` per slug. |
| `core.state_hub.GLOBAL_STATE_HUB` | TRADES (open), SYSTEM (bankroll/equity), GAME (position card) | In-memory; already the source of truth for live positions. |
| `trades_sports.db` (SQLite) | TRADES (closed today), HALL OF FAME (all stats) | Read-only; HOF queries are cached per page load. |
| ESPN scoreboard + detail | GAME (field rail tiles, header state, count/bases) | Caching logic lifted verbatim from `dashboard_server.py` into `core/espn_cache.py`. |
| `mlb_model/logs/shadow_recommendations.jsonl` | GAME (shadow rec line in position card) | Tail-read last N lines, match by slug. |
| `runtime/state.json` | SYSTEM (heartbeat, stale LED) | File mtime + JSON parse on demand. |

### Event bus (new — the only new moving part)

`dugout_dash/events.py`:

```python
class EventBus:
    def publish(self, event_type: str, payload: dict) -> None: ...
    def subscribe(self) -> queue.Queue: ...   # returns a new bounded queue
    def unsubscribe(self, q: queue.Queue) -> None: ...

GLOBAL_EVENT_BUS = EventBus()
```

Event types and payloads:

| event_type | payload | published by |
|---|---|---|
| `trade_entered` | `{trade_id, slug, side, price, size, game_id, team, ts}` | `bot_core.paper_fill()` after DB insert |
| `trade_exited` | `{trade_id, slug, exit_price, net_pnl, reason, ts}` | `bot_core.close_position()` after DB update |
| `mark_update` | `{slug, mark, prev_mark, ts}` | `market_tap.py` on every CLOB tick (one per slug at a time; coalesced at 5 Hz max to protect the browser) |
| `guard_state` | `{gates: [bool;9], bot_mode, ts}` | bot loop once per iteration |
| `heartbeat` | `{loop_ts, next_eta_s}` | bot loop every iteration |

### SSE endpoint

`GET /api/events` — `text/event-stream`. On connect: subscribes a fresh queue, writes one SSE frame per event received, heartbeats every 15 s. Max ~5 concurrent clients (operator only).

Client:
- Reconnects every 3 s on close; header chip shows `⚠ STALE` during disconnect.
- Dispatches each event to handlers registered by page-specific JS: e.g. `mark_update` → recompute P&L cells whose `data-slug` matches; `trade_entered` → toast + OS notify + play sound + prepend a row on TRADES.

### Realtime P&L recomputation

- Every position row renders with `data-slug`, `data-entry`, `data-size`, `data-side` attributes.
- `dugout.js` listens for `mark_update`; on receipt finds rows matching `data-slug` and recomputes `pnl = (mark - entry) * size * sign`, updates the cell's text, toggles `.pnl-up` / `.pnl-down`, and briefly adds `.flash-up` / `.flash-down` for a 300 ms pulse.
- No server-side P&L recompute for the live view. The server-rendered row provides the authoritative starting state; ticks after that are applied in the browser. Page refresh re-anchors from authoritative numbers.

---

## Pages

### `[ GAME ]` — `/` and `/game/<espn_id>`

**Layout:** 260 px left field rail · flexible main area split into top (tazz + position card) and bottom (orderbook + trade history for this game).

**Left rail — live game tiles.** One tile per ESPN game today. Content: teams (pixel font), score, inning, count. Selected tile gets the amber border. Tiles refresh every 20 s (SSE-free polling — ESPN changes too slowly to stream).

**Header strip (main area).** Score (pixel), inning + count + outs as dots (`●●○`).

**Tazz panel.** `<iframe src="{TAZZ_BASE_URL}/mlb/<derived-slug>" onload=tazzOk onerror=tazzFail>`. 3-second watchdog: if no load event, swap the iframe for a pixel-styled `▶ WATCH ON TAZZ` button that opens the same URL in a new tab. Tazz URL derivation: use ESPN team abbreviations (known format), e.g. `https://tazz.tv/mlb/nyy-vs-bos`. Exact URL template stored in `config.TAZZ_BASE_URL` so operator can correct it after seeing their login redirect.

**Position card.** If you have an open position on this game: the row `partials/pos_card.html` — market, entry, mark, size, P&L with live flash, age, shadow rec line, 9 guard gates as pixel lights. If no open position: collapsed card showing shadow rec only, plus a `STEP UP` button.

**Orderbook.** Top-5 bid/ask from `state_hub` → repainted on `mark_update` for the displayed slug.

**Trade history (this game).** Closed trades in this game, newest first, from `trades_sports.db`.

### `[ TRADES ]` — `/trades`

Two panels:

- **OPEN POSITIONS** — table: slug · team · entry · size · mark · P&L · P&L% · age · [CLOSE] button. P&L cell is the realtime-flash cell.
- **CLOSED TODAY** — collapsed by default, expandable: slug · entry · exit · net P&L · exit reason (TAKE_PROFIT / STOP_LOSS / SIGNAL / EXPIRY). "Today" = rolling 24 h to keep the page honest across game-day boundaries.

Each OPEN row prepends to the top when `trade_entered` arrives via SSE. Each CLOSED row appears when `trade_exited` arrives; the matching OPEN row animates out and is removed.

### `[ TAPE ]` — `/tape`

- **Top strip: NYSE-style ticker marquee.** One cell per active market's YES contract: `SLUG 54¢ ▲0.8`. Green arrow up / red arrow down based on last tick direction. CSS-based auto-scroll left at ~80 px/s; pauses on hover. Marquee re-renders the whole tape when the discovery cache refreshes (every ~60 s).
- **Main body: position-focused wide rows.** Same data as TRADES OPEN but wider — adds a 60-second pixel-art sparkline per position. Sparkline: 60 bars, 1 bar/sec, height = recent range normalized. Each row keeps a browser-side circular buffer (`Array(60)`) indexed by second; a 1 Hz setInterval snapshots the current mark into the next bucket and re-renders the SVG. New positions start with an empty buffer that fills over the first minute. No server-side sparkline storage.

### `[ SYSTEM ]` — `/system`

- **Bot heartbeat.** Last loop timestamp, last loop duration, stale LED `⚠ STALE` if no heartbeat in 90 s.
- **Guard gates.** 9 pixel lights with hover tooltips explaining each gate; amber if passing, red foul if blocking, dark if untested.
- **Bankroll / equity / today P&L / win rate today.**
- **Market stream status.** WS connected/reconnecting, messages/sec, coalesced tick rate.
- **SSE.** Current client count.
- **Controls.** `PAUSE BOT` / `RESUME BOT` / `FLAT ALL` — each opens a themed confirm modal (reuse control plane's modal pattern). These POST to bot_core's existing control flags in `runtime/state.json`.

### `[ HALL OF FAME ]` — `/hof`

Baseball-card grid — each card is one stat, rendered with pixel chrome.

| Card | Stat | Source |
|---|---|---|
| TEAM RECORDS | Table: team · W · L · P&L · batting avg | `SELECT team, SUM(win), SUM(loss)... FROM closed_trades GROUP BY team` |
| BATTING AVG | Career win rate, giant pixel number | `wins / (wins + losses)` all-time |
| SLUGGING | Avg winning-trade P&L | `AVG(net_pnl) WHERE net_pnl > 0` |
| ERA | Avg losing-trade P&L | `AVG(net_pnl) WHERE net_pnl < 0` |
| MVP DAY | Best single-day P&L (date + trade list) | `SELECT DATE(...), SUM(net_pnl) GROUP BY DATE ORDER BY 2 DESC LIMIT 1` |
| NO-HITTER | Count of 100%-win days + most recent date | grouped-by-day view |
| ROOKIE OF THE YEAR | Newest team (by first-traded date) with positive cumulative P&L | team-level cumulative |
| DYNASTY | Team with highest career P&L, trophy sprite, gold border | `SELECT team ORDER BY SUM(net_pnl) DESC LIMIT 1` |

All queries live in `hof_sql.py`, cached in memory for 60 s per page hit. Page has a `REFRESH` button that busts the cache. Adding a new card = one SQL + one template block.

---

## Data flow — realtime trade-entered example

```
bot_core.paper_fill(...)
  └─ DB INSERT trades_sports.db
  └─ GLOBAL_STATE_HUB.add_position(...)
  └─ GLOBAL_EVENT_BUS.publish("trade_entered", {...})            # new
                       └─ (in-process) EventBus fans out to N queues
                              └─ SSE handler writes frame to each client
                                     └─ browser dugout.js:
                                         • toast("BASE HIT — TRADE FILLED")
                                         • Notification("BUY YES · YANKEES @ 0.48")  (if permission granted)
                                         • play('base_hit.wav')
                                         • prepend trade_row to TRADES OPEN table
                                         • if current page is GAME for this game, insert into position card
```

Target latency budget: DB+hub ~10 ms, bus fanout ~1 ms, SSE flush ~20 ms, browser paint ~50 ms → well under 500 ms.

## Data flow — realtime mark_update

```
CLOB WebSocket tick  →  GLOBAL_MARKET_STREAM  →  market_tap.py subscriber
                                                    └─ coalesces to 5 Hz per slug
                                                    └─ EventBus.publish("mark_update", ...)
                                                           └─ SSE → dugout.js:
                                                                 • update orderbook top (GAME)
                                                                 • recompute every row with matching data-slug
                                                                 • flash-up / flash-down 300 ms
                                                                 • push a bar onto sparkline (TAPE)
                                                                 • update ticker cell (TAPE top strip)
```

Coalescing: collect ticks per slug, emit at most one `mark_update` per slug per 200 ms. Protects the browser under busy markets.

---

## Error handling

- **SSE drop.** Client auto-reconnects every 3 s; header shows `⚠ STALE`; `foul.wav` plays on first reconnect if the page was alive >15 s.
- **Market stream drop.** `SYSTEM` page shows red LED. TAPE cells freeze at last value. No stale P&L is served — frozen is better than lying.
- **ESPN fetch fail.** Field rail shows last successful snapshot with an `ESPN STALE` chip; do not blank out.
- **Tazz iframe blocked.** 3-second watchdog replaces iframe with deep-link button. Config flag `TAZZ_FORCE_LINK=1` skips the iframe entirely if operator finds iframe attempts slow the page.
- **DB lock / read error on HOF.** Show a single red panel "Hall of Fame unavailable" with retry; other pages unaffected.
- **Sound / Notification permission denied.** Toast still works. No sound, no OS notify. Never re-prompt — one request on first interaction.

---

## Testing

Run manually for UI; lean on small `pytest` suites for the non-UI pieces.

- `tests/test_event_bus.py` — publish / subscribe / unsubscribe, bounded queue overflow behavior, fanout to N subscribers.
- `tests/test_market_tap_coalesce.py` — 100 ticks in 50 ms for one slug → at most 1 emitted; multi-slug bursts don't interfere.
- `tests/test_hof_sql.py` — seeded in-memory SQLite with canned trades; each HOF query returns expected shape and values.
- `tests/test_tazz_url.py` — ESPN team abbrevs → tazz URL template.
- **Manual UI walkthrough (documented in plan):** open a trade via a synthetic bot run; verify toast + OS notify + sound + row + GAME card + TAPE ticker update all fire within 500 ms. Close the trade; verify exit flow. Kill the bot; verify stale LED. Restart; verify reconnect.

## Rollout / migration

1. **Phase 0 — Scaffold.** Create `dugout_dash/` with Flask app, base template, scoreboard header, empty blueprints. Runs on 8900 alongside existing `dashboard_server.py` (which moves temporarily to 8901 via `DASHBOARD_PORT=8901`) so we can A/B.
2. **Phase 1 — Event bus + SSE.** Wire `event_bus.publish` into `paper_fill` / `close_position`. Add market_tap. Prove SSE round-trip with a dev-only `/api/events/test` endpoint.
3. **Phase 2 — TRADES + TAPE.** These are the realtime-proof pages; ship them first with full SSE integration.
4. **Phase 3 — GAME.** Field rail, position card, tazz embed with fallback, orderbook.
5. **Phase 4 — SYSTEM + HALL OF FAME.** Lower-priority pages.
6. **Phase 5 — Cutover.** Delete `dashboard_server.py`, `dashboard.html`, `dashboard_v2.html`. `DASHBOARD_PORT=8900` is permanently dugout_dash.

Each phase ends with operator-verified "trade on a synthetic run feels snappy and correct."

## Out of scope (explicit)

- Replaying historical games in the UI.
- Editing `.env` or bot config from the UI.
- Any tazz.tv feature beyond embed-with-fallback (no stream scraping, no chat integration, no authentication handling).
- Mobile layout.
- Multi-user permissions.
- Exporting Hall of Fame cards as images/PNG.
- Persona system (Haiku/Sonnet/Opus characters) — the control plane owns that; dugout_dash is bot-watching, not agent-watching.

## Open questions to track during implementation

1. **Tazz URL template.** We'll discover the exact format when the operator opens their first authenticated game. Config-driven so no code change required.
2. **Sound asset licensing.** Use CC0/public-domain 8-bit SFX (freesound.org / opengameart); verify each file's license before shipping.
3. **HOF query cost at scale.** After 1,000+ closed trades, re-check whether 60 s cache is enough or we need materialized views.
