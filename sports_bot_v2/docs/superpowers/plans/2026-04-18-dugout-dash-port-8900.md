# Dugout Dash (port 8900) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the stdlib `dashboard_server.py` on port 8900 with a Flask app `dugout_dash` that adopts the DUGOUT OS 8-bit aesthetic, serves 5 pages (GAME, TRADES, TAPE, SYSTEM, HALL OF FAME), streams trade + price events to the browser via SSE, and ships realtime P&L updates + toast/OS/sound notifications on trade entries.

**Architecture:** New Flask package `sports_bot_v2/dugout_dash/` with blueprints per page, an in-process `EventBus` that fans out `trade_entered` / `trade_exited` / `mark_update` events to every SSE-connected browser, a `market_tap` subscriber that coalesces CLOB ticks to 5 Hz per slug, and two tiny instrumentation points in `bot_core.py` that publish trade events. Reuses existing `core.market_stream`, `core.state_hub`, `core.db`, and the ESPN caching already present in `dashboard_server.py`. Design doc: `docs/superpowers/specs/2026-04-18-dugout-dash-port-8900-design.md`.

**Tech Stack:** Python 3.11+, Flask, stdlib `queue`/`threading` for EventBus, Jinja2 templates, vanilla JS (no framework), `Press Start 2P` + `VT323` web fonts, SQLite (existing), SSE over plain HTTP.

---

## File Structure

**Create:**
- `sports_bot_v2/dugout_dash/__init__.py` — `create_app()` factory, runs the market_tap thread on startup
- `sports_bot_v2/dugout_dash/config.py` — port, paths, tazz URL template, coalesce settings
- `sports_bot_v2/dugout_dash/events.py` — `EventBus` class + `GLOBAL_EVENT_BUS` singleton
- `sports_bot_v2/dugout_dash/market_tap.py` — subscribes to `GLOBAL_STATE_HUB` mark updates via polling, republishes to EventBus with coalescing
- `sports_bot_v2/dugout_dash/hof_sql.py` — all Hall of Fame queries + in-memory 60 s cache
- `sports_bot_v2/dugout_dash/blueprints/__init__.py`
- `sports_bot_v2/dugout_dash/blueprints/game.py` — `/` and `/game/<espn_id>` routes
- `sports_bot_v2/dugout_dash/blueprints/trades.py` — `/trades`
- `sports_bot_v2/dugout_dash/blueprints/tape.py` — `/tape`
- `sports_bot_v2/dugout_dash/blueprints/system.py` — `/system` and POST controls
- `sports_bot_v2/dugout_dash/blueprints/hof.py` — `/hof` and `/hof/refresh`
- `sports_bot_v2/dugout_dash/blueprints/api.py` — `/api/events` (SSE), `/api/trades.json`, `/api/tape.json`, `/api/games.json`
- `sports_bot_v2/dugout_dash/run.py` — `python -m dugout_dash.run` entry point
- `sports_bot_v2/dugout_dash/templates/base.html`
- `sports_bot_v2/dugout_dash/templates/partials/game_tile.html`
- `sports_bot_v2/dugout_dash/templates/partials/trade_row.html`
- `sports_bot_v2/dugout_dash/templates/partials/ticker_cell.html`
- `sports_bot_v2/dugout_dash/templates/partials/pos_card.html`
- `sports_bot_v2/dugout_dash/templates/game.html`
- `sports_bot_v2/dugout_dash/templates/trades.html`
- `sports_bot_v2/dugout_dash/templates/tape.html`
- `sports_bot_v2/dugout_dash/templates/system.html`
- `sports_bot_v2/dugout_dash/templates/hof.html`
- `sports_bot_v2/dugout_dash/static/app.css` — pixel chrome (lifted from mlbbot/control_plane/static/app.css) + dash additions
- `sports_bot_v2/dugout_dash/static/dugout.js` — SSE client, toast, Notification API, sound player, P&L recomputation, sparkline
- `sports_bot_v2/dugout_dash/static/sounds/base_hit.wav` — CC0 SFX
- `sports_bot_v2/dugout_dash/static/sounds/strikeout.wav`
- `sports_bot_v2/dugout_dash/static/sounds/walkoff.wav`
- `sports_bot_v2/dugout_dash/static/sounds/foul.wav`
- `sports_bot_v2/core/espn_cache.py` — extracted ESPN fetcher module
- `sports_bot_v2/tests/dugout_dash/test_event_bus.py`
- `sports_bot_v2/tests/dugout_dash/test_market_tap_coalesce.py`
- `sports_bot_v2/tests/dugout_dash/test_hof_sql.py`
- `sports_bot_v2/tests/dugout_dash/test_tazz_url.py`
- `sports_bot_v2/tests/dugout_dash/test_sse_endpoint.py`
- `sports_bot_v2/tests/dugout_dash/__init__.py`
- `sports_bot_v2/tests/__init__.py` (if missing)

**Modify:**
- `sports_bot_v2/bot_core.py:782` — publish `trade_entered` after successful `insert_open_trade`
- `sports_bot_v2/bot_core.py:1069` — publish `trade_exited` after `close_trade`
- `sports_bot_v2/requirements.txt` (or `pyproject.toml`) — add `flask>=3.0`
- `sports_bot_v2/.env.example` — document new env vars (`DUGOUT_DASH_PORT`, `TAZZ_BASE_URL`, etc.)

**Delete (Phase 5 only):**
- `sports_bot_v2/dashboard_server.py`
- `sports_bot_v2/dashboard.html`
- `sports_bot_v2/dashboard_v2.html`

---

## Phase 0 — Scaffold (Tasks 1–5)

### Task 1: Create test layout + Flask dependency

**Files:**
- Create: `sports_bot_v2/tests/dugout_dash/__init__.py` (empty)
- Modify: `sports_bot_v2/requirements.txt`

- [ ] **Step 1: Create empty test package**

```bash
mkdir -p /c/Users/johnny/Desktop/sports_bot_v2/tests/dugout_dash
touch /c/Users/johnny/Desktop/sports_bot_v2/tests/dugout_dash/__init__.py
touch /c/Users/johnny/Desktop/sports_bot_v2/tests/__init__.py
```

- [ ] **Step 2: Check for requirements file**

```bash
cat /c/Users/johnny/Desktop/sports_bot_v2/requirements.txt 2>/dev/null || echo "MISSING"
```

Expected: either content is shown or "MISSING". If missing, create it.

- [ ] **Step 3: Add Flask to requirements**

Append these lines to `requirements.txt` (create file if it doesn't exist):
```
flask>=3.0,<4.0
```

- [ ] **Step 4: Install**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && pip install flask
```

Expected: `Successfully installed flask-3.x.x ...` or already satisfied.

- [ ] **Step 5: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add tests/__init__.py tests/dugout_dash/__init__.py requirements.txt && git commit -m "chore(dugout_dash): scaffold test package, add flask dep"
```

---

### Task 2: Minimal Flask app factory + run entry

**Files:**
- Create: `sports_bot_v2/dugout_dash/__init__.py`
- Create: `sports_bot_v2/dugout_dash/config.py`
- Create: `sports_bot_v2/dugout_dash/run.py`

- [ ] **Step 1: Write config**

Create `sports_bot_v2/dugout_dash/config.py`:
```python
"""dugout_dash config — env-driven."""
from __future__ import annotations
import os
from pathlib import Path


def _env_int(k: str, default: int) -> int:
    try:
        return int(os.getenv(k, default))
    except (TypeError, ValueError):
        return default


def _env_float(k: str, default: float) -> float:
    try:
        return float(os.getenv(k, default))
    except (TypeError, ValueError):
        return default


PORT = _env_int("DUGOUT_DASH_PORT", _env_int("DASHBOARD_PORT", 8900))
HOST = os.getenv("DUGOUT_DASH_HOST", "0.0.0.0")
DB_PATH = os.getenv("DB_PATH", "trades_sports.db")
STATE_PATH = os.getenv("STATE_PATH", "runtime/state.json")
SPORT = os.getenv("SPORT", "baseball")
STARTING_BANKROLL = _env_float("STARTING_BANKROLL", 500.0)

# Tazz: {slug} is replaced with computed ESPN-derived slug, e.g. "nyy-vs-bos"
TAZZ_BASE_URL = os.getenv("TAZZ_BASE_URL", "https://tazz.tv/mlb/{slug}")
TAZZ_FORCE_LINK = os.getenv("TAZZ_FORCE_LINK", "0") == "1"
TAZZ_IFRAME_TIMEOUT_MS = _env_int("TAZZ_IFRAME_TIMEOUT_MS", 3000)

# Coalescing
MARK_UPDATE_HZ = _env_float("DUGOUT_MARK_UPDATE_HZ", 5.0)   # emit at most 5 mark_updates/slug/sec
HOF_CACHE_TTL_SEC = _env_int("DUGOUT_HOF_CACHE_TTL", 60)

# MLB model shadow recs
SHADOW_LOG_PATH = os.getenv(
    "MLB_SHADOW_LOG_PATH",
    str(Path(__file__).resolve().parents[2] / "mlb_model" / "logs" / "shadow_recommendations.jsonl"),
)
```

- [ ] **Step 2: Write app factory**

Create `sports_bot_v2/dugout_dash/__init__.py`:
```python
"""dugout_dash — Flask app factory."""
from __future__ import annotations
from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["JSON_SORT_KEYS"] = False

    # Blueprints are registered in later tasks; placeholder root for now.
    @app.route("/healthz")
    def healthz():
        return {"ok": True, "app": "dugout_dash"}

    return app
```

- [ ] **Step 3: Write run entry**

Create `sports_bot_v2/dugout_dash/run.py`:
```python
"""python -m dugout_dash.run — start the live dashboard."""
from __future__ import annotations
import logging
from dugout_dash import create_app
from dugout_dash.config import HOST, PORT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [DUGOUT] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> None:
    app = create_app()
    # threaded=True → SSE can stream while request handlers also run.
    app.run(host=HOST, port=PORT, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Start the app (temporarily on 8901 so we don't collide)**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && DUGOUT_DASH_PORT=8901 python -m dugout_dash.run &
sleep 2
curl -s http://127.0.0.1:8901/healthz
```

Expected: `{"ok": true, "app": "dugout_dash"}`

Kill the process:
```bash
pkill -f "dugout_dash.run" 2>/dev/null || true
```

- [ ] **Step 5: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add dugout_dash/__init__.py dugout_dash/config.py dugout_dash/run.py && git commit -m "feat(dugout_dash): Flask app factory + /healthz + run entry"
```

---

### Task 3: Lift pixel CSS from control plane

**Files:**
- Create: `sports_bot_v2/dugout_dash/static/app.css`

- [ ] **Step 1: Copy the pixel chrome section**

Copy `C:\Users\johnny\Desktop\mlbbot\control_plane\static\app.css` — specifically the section starting with the comment `/* === DUGOUT OS — scoreboard shell === */` (around line 1052) through the end of the ticker/ribbon styles. The `:root` block containing `--scoreboard-amber`, `--scoreboard-green`, `--field-night`, `--chalk`, etc. (around line 982) is also required.

Save as `sports_bot_v2/dugout_dash/static/app.css`. Keep only the `:root` vars, base body styles, `.scoreboard`, `.brand-pixel`, `.chip-pixel*`, `.scoreboard-*`, `.nav-tab`, `.role-switch-pixel`, `.btn-pixel*`, `.cta-step-up`, `.between-innings-ticker`/`ticker-*`, `.led-ribbon`. Drop: everything under `.board`, `.lane`, `.card`, `.task-card-trading`, `.confirm-modal`, `.chip-active/queued/blocked/done`, `.priority-*`, `.filters`, `.counts`, and anything referencing `persona-*` — those belong to the control plane board and we don't need them here.

- [ ] **Step 2: Append dugout-dash additions**

At the end of `app.css`, append:
```css
/* ============================================================
 * dugout_dash additions — not in control plane
 * ============================================================ */

.dash-shell { display: grid; grid-template-columns: 260px 1fr; min-height: calc(100vh - 120px); }
.field-rail { background: var(--field-deep); border-right: 2px solid var(--scoreboard-amber); padding: 12px 10px; overflow-y: auto; }
.rail-title { font-family: var(--font-pixel); font-size: 9px; color: var(--scoreboard-amber); letter-spacing: .08em; margin-bottom: 10px; }

.game-tile { display: block; background: rgba(0,0,0,.35); border: 1px solid var(--chalk-dim); padding: 8px 10px; margin-bottom: 8px; font-family: var(--font-pixel-text); font-size: 16px; line-height: 1.2; cursor: pointer; color: var(--chalk); text-decoration: none; }
.game-tile.selected { border-color: var(--scoreboard-amber); box-shadow: inset 0 0 0 1px var(--scoreboard-amber); }
.game-tile .teams { font-family: var(--font-pixel); font-size: 10px; color: var(--chalk); margin-bottom: 4px; }
.game-tile .state { color: var(--scoreboard-amber); }

.pane { padding: 16px 20px; }
.main-grid { display: grid; grid-template-columns: 1fr 360px; gap: 16px; }

.tazz-panel { aspect-ratio: 16/9; background: #000; border: 2px solid var(--scoreboard-amber); display: flex; align-items: center; justify-content: center; position: relative; overflow: hidden; }
.tazz-panel iframe { width: 100%; height: 100%; border: 0; }
.tazz-fallback { text-align: center; }
.tazz-watch-btn { font-family: var(--font-pixel); font-size: 14px; background: var(--turf); color: var(--chalk); border: 2px solid var(--hr-gold); padding: 14px 22px; letter-spacing: .05em; text-decoration: none; display: inline-block; }
.tazz-sub { font-family: var(--font-pixel-text); font-size: 18px; color: var(--chalk-dim); margin-top: 10px; }

.pos-card { background: rgba(0,0,0,.35); border: 2px solid var(--scoreboard-green); padding: 14px; }
.pos-card h3 { font-family: var(--font-pixel); font-size: 11px; color: var(--scoreboard-amber); margin: 0 0 10px; letter-spacing: .06em; }
.pos-row { display: flex; justify-content: space-between; font-family: var(--font-pixel-text); font-size: 20px; padding: 4px 0; border-bottom: 1px dotted rgba(255,255,255,.1); }
.pos-row .k { color: var(--chalk-dim); }
.pos-row .v { color: var(--chalk); }
.pnl-up   { color: var(--scoreboard-green); }
.pnl-down { color: var(--foul-red); }
.flash-up   { animation: flashUp .4s ease; }
.flash-down { animation: flashDown .4s ease; }
@keyframes flashUp   { 0% { background: rgba(125,216,125,.35); } 100% { background: transparent; } }
@keyframes flashDown { 0% { background: rgba(230,57,70,.35);   } 100% { background: transparent; } }

.gates { display: flex; gap: 6px; margin-top: 8px; }
.gate { width: 12px; height: 12px; border-radius: 50%; background: #222; border: 1px solid var(--chalk-dim); }
.gate.on  { background: var(--scoreboard-green); border-color: var(--scoreboard-green); box-shadow: 0 0 6px var(--scoreboard-green); }
.gate.off { background: var(--foul-red); border-color: var(--foul-red); }

.panel { background: rgba(0,0,0,.35); border: 1px solid var(--chalk-dim); padding: 12px; }
.panel h3 { font-family: var(--font-pixel); font-size: 11px; color: var(--scoreboard-amber); margin: 0 0 10px; letter-spacing: .06em; }
.panel table { width: 100%; border-collapse: collapse; font-family: var(--font-pixel-text); font-size: 18px; }
.panel th, .panel td { text-align: left; padding: 4px 6px; border-bottom: 1px dotted rgba(255,255,255,.08); }
.panel th { color: var(--chalk-dim); font-family: var(--font-pixel); font-size: 9px; letter-spacing: .05em; text-transform: uppercase; }

/* Tape marquee */
.tape-marquee { overflow: hidden; white-space: nowrap; border-top: 2px solid var(--scoreboard-amber); border-bottom: 2px solid var(--scoreboard-amber); background: var(--field-deep); padding: 6px 0; }
.tape-track { display: inline-block; animation: tapeScroll 80s linear infinite; }
.tape-track:hover { animation-play-state: paused; }
@keyframes tapeScroll { from { transform: translateX(0); } to { transform: translateX(-50%); } }
.ticker-cell { display: inline-block; font-family: var(--font-pixel-text); font-size: 20px; padding: 0 24px; color: var(--chalk); }
.ticker-cell .up   { color: var(--scoreboard-green); }
.ticker-cell .down { color: var(--foul-red); }

/* Sparkline */
.sparkline { width: 240px; height: 40px; }

/* Toast */
#toast-root { position: fixed; right: 20px; bottom: 20px; display: flex; flex-direction: column; gap: 10px; z-index: 200; }
.toast { background: var(--field-deep); border: 2px solid var(--scoreboard-green); padding: 14px 18px; font-family: var(--font-pixel-text); font-size: 20px; color: var(--chalk); box-shadow: 0 0 24px rgba(125,216,125,.35); opacity: 0; transform: translateY(10px); transition: opacity .2s ease, transform .2s ease; }
.toast.show { opacity: 1; transform: translateY(0); }
.toast.err  { border-color: var(--foul-red); box-shadow: 0 0 24px rgba(230,57,70,.35); }
.toast .title { font-family: var(--font-pixel); font-size: 10px; color: var(--scoreboard-green); letter-spacing: .08em; margin-bottom: 6px; }
.toast.err .title { color: var(--foul-red); }

/* SSE health */
.chip-stale { color: var(--foul-red); border-color: var(--foul-red); }
```

- [ ] **Step 3: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add dugout_dash/static/app.css && git commit -m "feat(dugout_dash): DUGOUT OS pixel CSS lifted from control plane + dash additions"
```

---

### Task 4: Base template (scoreboard header + nav + footer)

**Files:**
- Create: `sports_bot_v2/dugout_dash/templates/base.html`

- [ ] **Step 1: Write base.html**

Create `sports_bot_v2/dugout_dash/templates/base.html`:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{% block title %}Dugout Dash · sports_bot_v2{% endblock %}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Press+Start+2P&family=VT323&family=Inter+Tight:wght@400;500;600;700&display=swap">
  <link rel="stylesheet" href="{{ url_for('static', filename='app.css') }}">
</head>
<body>

<header class="scoreboard">
  <div class="scoreboard-left">
    <a href="{{ url_for('game.index') }}" class="brand-pixel">
      <span class="brand-pixel-line1">DUGOUT DASH</span>
      <span class="brand-pixel-line2">sports_bot_v2 · {{ PORT }}</span>
    </a>
    <span class="chip-pixel-led" title="Bot version">● BOT v{{ BOT_VERSION|default('0.4.2') }}</span>
    <span class="chip-pixel-led" title="Live games">⚾ {{ LIVE_COUNT|default(0) }}</span>
    <span class="chip-pixel-led" title="Open positions">💼 {{ OPEN_COUNT|default(0) }}</span>
    <span id="sse-chip" class="chip-pixel chip-pixel--ok" title="Realtime stream">✓ LIVE</span>
  </div>

  <nav class="scoreboard-nav">
    <a href="{{ url_for('game.index') }}"   class="nav-tab {% if ACTIVE=='game' %}active{% endif %}">[ GAME ]</a>
    <a href="{{ url_for('trades.index') }}" class="nav-tab {% if ACTIVE=='trades' %}active{% endif %}">[ TRADES ]</a>
    <a href="{{ url_for('tape.index') }}"   class="nav-tab {% if ACTIVE=='tape' %}active{% endif %}">[ TAPE ]</a>
    <a href="{{ url_for('system.index') }}" class="nav-tab {% if ACTIVE=='system' %}active{% endif %}">[ SYSTEM ]</a>
    <a href="{{ url_for('hof.index') }}"    class="nav-tab {% if ACTIVE=='hof' %}active{% endif %}">[ HALL OF FAME ]</a>
  </nav>

  <div class="scoreboard-right">
    <span class="chip-pixel-led">💰 ${{ '%.2f'|format(BANKROLL|default(0.0)) }}</span>
    <span class="chip-pixel-led">{% if TODAY_PNL is not none %}{% if TODAY_PNL >= 0 %}<span class="pnl-up">+${{ '%.2f'|format(TODAY_PNL) }}</span>{% else %}<span class="pnl-down">-${{ '%.2f'|format(-TODAY_PNL) }}</span>{% endif %}{% endif %}</span>
  </div>
</header>

<main>
{% block content %}{% endblock %}
</main>

<footer class="led-ribbon">
  <span>repo sports_bot_v2</span>
  <span>·</span>
  <span>db {{ DB_PATH }}</span>
  <span>·</span>
  <span>port {{ PORT }}</span>
  <span>·</span>
  <span id="sse-client-count">sse clients —</span>
</footer>

<div id="toast-root"></div>

<script src="{{ url_for('static', filename='dugout.js') }}"></script>
{% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 2: Create stub dugout.js (real version in Task 17)**

Create `sports_bot_v2/dugout_dash/static/dugout.js`:
```js
// dugout.js — stub; real SSE + toast + sound logic wired in Task 17.
console.log("dugout.js loaded — stub");
```

- [ ] **Step 3: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add dugout_dash/templates/base.html dugout_dash/static/dugout.js && git commit -m "feat(dugout_dash): base scoreboard template + JS stub"
```

---

### Task 5: Game blueprint stub + smoke test the shell

**Files:**
- Create: `sports_bot_v2/dugout_dash/blueprints/__init__.py` (empty)
- Create: `sports_bot_v2/dugout_dash/blueprints/game.py`
- Create: `sports_bot_v2/dugout_dash/templates/game.html`
- Modify: `sports_bot_v2/dugout_dash/__init__.py`

- [ ] **Step 1: Create blueprints package**

```bash
echo "" > /c/Users/johnny/Desktop/sports_bot_v2/dugout_dash/blueprints/__init__.py
```

- [ ] **Step 2: Write game blueprint stub**

Create `sports_bot_v2/dugout_dash/blueprints/game.py`:
```python
"""GAME page blueprint — landing + per-game detail."""
from __future__ import annotations
from flask import Blueprint, render_template

bp = Blueprint("game", __name__)


@bp.route("/")
def index():
    return render_template(
        "game.html",
        ACTIVE="game",
        GAMES=[],        # filled in Task 20
        SELECTED=None,
    )


@bp.route("/game/<espn_id>")
def detail(espn_id: str):
    return render_template(
        "game.html",
        ACTIVE="game",
        GAMES=[],
        SELECTED=espn_id,
    )
```

- [ ] **Step 3: Write game.html stub**

Create `sports_bot_v2/dugout_dash/templates/game.html`:
```html
{% extends "base.html" %}
{% block title %}GAME · Dugout Dash{% endblock %}
{% block content %}
<div class="dash-shell">
  <aside class="field-rail">
    <div class="rail-title">── FIELD ──</div>
    {% if not GAMES %}<div class="rail-title" style="color: var(--chalk-dim);">no live games</div>{% endif %}
  </aside>
  <section class="pane">
    <h2 style="font-family: var(--font-pixel); color: var(--scoreboard-amber);">GAME</h2>
    <p style="font-family: var(--font-pixel-text); font-size: 20px;">
      (field rail, tazz embed, position card, orderbook, trade history — filled in later tasks)
    </p>
  </section>
</div>
{% endblock %}
```

- [ ] **Step 4: Register blueprint in factory**

Edit `sports_bot_v2/dugout_dash/__init__.py`:
```python
"""dugout_dash — Flask app factory."""
from __future__ import annotations
from flask import Flask

from dugout_dash import config as cfg
from dugout_dash.blueprints import game as game_bp


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["JSON_SORT_KEYS"] = False

    @app.context_processor
    def inject_globals():
        return {
            "PORT": cfg.PORT,
            "DB_PATH": cfg.DB_PATH,
            "BOT_VERSION": "0.4.2",
            "BANKROLL": cfg.STARTING_BANKROLL,
            "TODAY_PNL": 0.0,
            "LIVE_COUNT": 0,
            "OPEN_COUNT": 0,
        }

    app.register_blueprint(game_bp.bp)

    @app.route("/healthz")
    def healthz():
        return {"ok": True, "app": "dugout_dash"}

    return app
```

- [ ] **Step 5: Smoke test visually**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && DUGOUT_DASH_PORT=8901 python -m dugout_dash.run &
sleep 2
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8901/
```

Expected: `200`. Open `http://127.0.0.1:8901/` in a browser — should show the pixel scoreboard header with `[ GAME ] [ TRADES ] [ TAPE ] [ SYSTEM ] [ HALL OF FAME ]` (the last 4 will 404 until registered), the "no live games" field rail, and the placeholder pane.

Kill: `pkill -f dugout_dash.run 2>/dev/null || true`

- [ ] **Step 6: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add dugout_dash/blueprints/__init__.py dugout_dash/blueprints/game.py dugout_dash/templates/game.html dugout_dash/__init__.py && git commit -m "feat(dugout_dash): game blueprint stub + visible scoreboard shell"
```

---

## Phase 1 — Event bus + SSE (Tasks 6–10)

### Task 6: EventBus with bounded per-client queues

**Files:**
- Create: `sports_bot_v2/dugout_dash/events.py`
- Create: `sports_bot_v2/tests/dugout_dash/test_event_bus.py`

- [ ] **Step 1: Write the failing test**

Create `sports_bot_v2/tests/dugout_dash/test_event_bus.py`:
```python
"""EventBus tests — publish/subscribe/unsubscribe + overflow behavior."""
import time

import pytest

from dugout_dash.events import EventBus


def test_publish_delivers_to_single_subscriber():
    bus = EventBus()
    q = bus.subscribe()
    bus.publish("trade_entered", {"id": 42})
    evt = q.get(timeout=0.5)
    assert evt == {"type": "trade_entered", "payload": {"id": 42}}


def test_publish_fans_out_to_all_subscribers():
    bus = EventBus()
    q1, q2, q3 = bus.subscribe(), bus.subscribe(), bus.subscribe()
    bus.publish("mark_update", {"slug": "foo", "mark": 0.5})
    for q in (q1, q2, q3):
        evt = q.get(timeout=0.5)
        assert evt["type"] == "mark_update"
        assert evt["payload"]["slug"] == "foo"


def test_unsubscribe_removes_queue():
    bus = EventBus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()
    bus.unsubscribe(q1)
    bus.publish("x", {})
    assert q2.qsize() == 1
    # q1 should not receive the new event
    assert q1.qsize() == 0


def test_overflow_drops_oldest_when_queue_full():
    bus = EventBus(max_queue_size=3)
    q = bus.subscribe()
    for i in range(5):
        bus.publish("tick", {"i": i})
    # Only the 3 most recent should be in the queue
    received = [q.get_nowait()["payload"]["i"] for _ in range(3)]
    assert received == [2, 3, 4]


def test_publish_is_nonblocking_under_load():
    bus = EventBus(max_queue_size=10)
    bus.subscribe()  # never drains
    start = time.monotonic()
    for _ in range(1000):
        bus.publish("x", {})
    elapsed = time.monotonic() - start
    assert elapsed < 0.5, f"publish blocked for {elapsed:.3f}s under back-pressure"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && python -m pytest tests/dugout_dash/test_event_bus.py -v
```

Expected: `ImportError` / `ModuleNotFoundError` — events module not yet created.

- [ ] **Step 3: Implement EventBus**

Create `sports_bot_v2/dugout_dash/events.py`:
```python
"""In-process pub/sub bus for dugout_dash.

Publish is non-blocking: if a subscriber's queue is full the oldest frame
is dropped. Subscribers get a bounded queue they drain on their own
schedule (typically one SSE connection per subscriber).
"""
from __future__ import annotations

import queue
import threading
from typing import Any


class EventBus:
    def __init__(self, max_queue_size: int = 256) -> None:
        self._max = max_queue_size
        self._subs: list[queue.Queue] = []
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=self._max)
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            try:
                self._subs.remove(q)
            except ValueError:
                pass

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subs)

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        frame = {"type": event_type, "payload": payload}
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            self._offer(q, frame)

    def _offer(self, q: queue.Queue, frame: dict) -> None:
        try:
            q.put_nowait(frame)
        except queue.Full:
            try:
                q.get_nowait()   # drop oldest
            except queue.Empty:
                pass
            try:
                q.put_nowait(frame)
            except queue.Full:
                pass  # give up; next publish will try again


GLOBAL_EVENT_BUS = EventBus()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && python -m pytest tests/dugout_dash/test_event_bus.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add dugout_dash/events.py tests/dugout_dash/test_event_bus.py && git commit -m "feat(dugout_dash): EventBus with bounded queues + overflow drop-oldest"
```

---

### Task 7: API blueprint with SSE endpoint

**Files:**
- Create: `sports_bot_v2/dugout_dash/blueprints/api.py`
- Create: `sports_bot_v2/tests/dugout_dash/test_sse_endpoint.py`
- Modify: `sports_bot_v2/dugout_dash/__init__.py`

- [ ] **Step 1: Write the failing test**

Create `sports_bot_v2/tests/dugout_dash/test_sse_endpoint.py`:
```python
"""SSE endpoint smoke test — connects, receives a published event, disconnects."""
import threading
import time

import pytest

from dugout_dash import create_app
from dugout_dash.events import GLOBAL_EVENT_BUS


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_sse_receives_published_event(client):
    # Start SSE request in a thread; it blocks streaming.
    chunks: list[bytes] = []

    def reader():
        with client.get("/api/events", buffered=False) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("Content-Type", "")
            # Read up to ~2 seconds worth of chunks.
            deadline = time.monotonic() + 2.0
            for chunk in resp.response:
                chunks.append(chunk)
                if time.monotonic() > deadline:
                    break

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    time.sleep(0.3)  # let the subscriber register

    GLOBAL_EVENT_BUS.publish("test_event", {"hello": "world"})
    t.join(timeout=3.0)

    body = b"".join(chunks).decode()
    assert "event: test_event" in body
    assert '"hello": "world"' in body or '"hello":"world"' in body
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && python -m pytest tests/dugout_dash/test_sse_endpoint.py -v
```

Expected: 404 or ImportError — api blueprint not registered.

- [ ] **Step 3: Implement API blueprint with SSE**

Create `sports_bot_v2/dugout_dash/blueprints/api.py`:
```python
"""API blueprint — SSE endpoint + JSON endpoints."""
from __future__ import annotations

import json
import queue
import time

from flask import Blueprint, Response, stream_with_context

from dugout_dash.events import GLOBAL_EVENT_BUS

bp = Blueprint("api", __name__, url_prefix="/api")

HEARTBEAT_SEC = 15.0
QUEUE_POLL_SEC = 0.5


@bp.route("/events")
def events_stream():
    def gen():
        q = GLOBAL_EVENT_BUS.subscribe()
        try:
            # Send a hello frame immediately so clients know they're live.
            yield _format_sse("hello", {"subscribers": GLOBAL_EVENT_BUS.subscriber_count()})
            last_beat = time.monotonic()
            while True:
                try:
                    frame = q.get(timeout=QUEUE_POLL_SEC)
                    yield _format_sse(frame["type"], frame["payload"])
                except queue.Empty:
                    pass
                now = time.monotonic()
                if now - last_beat > HEARTBEAT_SEC:
                    yield ": ping\n\n"
                    last_beat = now
        finally:
            GLOBAL_EVENT_BUS.unsubscribe(q)

    return Response(
        stream_with_context(gen()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _format_sse(event_type: str, payload: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
```

- [ ] **Step 4: Register blueprint**

Edit `sports_bot_v2/dugout_dash/__init__.py` — add next to game blueprint registration:
```python
from dugout_dash.blueprints import api as api_bp
# ...
app.register_blueprint(api_bp.bp)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && python -m pytest tests/dugout_dash/test_sse_endpoint.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add dugout_dash/blueprints/api.py tests/dugout_dash/test_sse_endpoint.py dugout_dash/__init__.py && git commit -m "feat(dugout_dash): SSE /api/events endpoint with heartbeat"
```

---

### Task 8: Wire trade_entered + trade_exited publishes in bot_core

**Files:**
- Modify: `sports_bot_v2/bot_core.py` (around lines 782 and 1069)

- [ ] **Step 1: Inspect current call sites**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && sed -n '780,790p' bot_core.py
cd /c/Users/johnny/Desktop/sports_bot_v2 && sed -n '1065,1075p' bot_core.py
```

Confirm the lines still look like:
- `trade_id = insert_open_trade(trade, sport=SPORT)` (~line 782)
- `close_trade(trade.id, close_data)` (~line 1069)

- [ ] **Step 2: Add import near the top of bot_core.py**

Find the block of `from core...` imports and append:
```python
try:
    from dugout_dash.events import GLOBAL_EVENT_BUS as _DUGOUT_BUS
except Exception:
    _DUGOUT_BUS = None  # dash not installed? bot still runs.
```

- [ ] **Step 3: Publish trade_entered after insert_open_trade**

Immediately **after** the `trade_id = insert_open_trade(trade, sport=SPORT)` line (~782), before the `if trade_id is None:` check, insert:

```python
if trade_id is not None and _DUGOUT_BUS is not None:
    try:
        _DUGOUT_BUS.publish("trade_entered", {
            "trade_id": trade_id,
            "slug": trade.market_slug,
            "market_id": trade.market_id,
            "side": trade.side,
            "entry_px": float(trade.entry_px or 0.0),
            "qty": float(trade.qty or 0.0),
            "size_usd": float(trade.qty or 0.0) * float(trade.entry_px or 0.0),
            "confidence": float(trade.confidence or 0.0),
            "mode": trade.mode,
            "ts": trade.ts_open,
            "sport": SPORT,
        })
    except Exception as e:
        logger.warning("dugout bus publish failed (trade_entered): %s", e)
```

- [ ] **Step 4: Publish trade_exited after close_trade**

Immediately **after** the `close_trade(trade.id, close_data)` line (~1069), insert:

```python
if _DUGOUT_BUS is not None:
    try:
        _DUGOUT_BUS.publish("trade_exited", {
            "trade_id": trade.id,
            "slug": trade.market_slug,
            "side": trade.side,
            "entry_px": float(trade.entry_px or 0.0),
            "exit_px": float(close_data.get("exit_px") or 0.0),
            "net_pnl": float(close_data.get("pnl_usd") or 0.0),
            "reason": close_data.get("reason_close") or reason,
            "ts": close_data.get("ts_close"),
            "sport": SPORT,
        })
    except Exception as e:
        logger.warning("dugout bus publish failed (trade_exited): %s", e)
```

- [ ] **Step 5: Smoke test — import still works**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && python -c "import bot_core; print('import ok')"
```

Expected: `import ok`. (The bot won't actually run during this test, we're just verifying syntax + imports.)

- [ ] **Step 6: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add bot_core.py && git commit -m "feat(bot_core): publish trade_entered/exited to dugout EventBus"
```

---

### Task 9: market_tap — coalesce CLOB ticks into mark_update events

**Files:**
- Create: `sports_bot_v2/dugout_dash/market_tap.py`
- Create: `sports_bot_v2/tests/dugout_dash/test_market_tap_coalesce.py`

- [ ] **Step 1: Write the failing test**

Create `sports_bot_v2/tests/dugout_dash/test_market_tap_coalesce.py`:
```python
"""market_tap coalescing — at most one mark_update per slug per interval."""
import time

from dugout_dash.events import EventBus
from dugout_dash.market_tap import MarketTap


def test_single_slug_burst_coalesces_to_one_per_interval():
    bus = EventBus()
    q = bus.subscribe()
    tap = MarketTap(bus=bus, interval_sec=0.2)

    # 50 ticks in ~50ms — all for the same slug.
    for i in range(50):
        tap.feed({"foo": {"current_price": 0.50 + i * 0.001}})

    tap.flush_if_due()
    # Only the most recent mark for foo should be emitted.
    frames = []
    while not q.empty():
        frames.append(q.get_nowait())
    assert len(frames) == 1
    assert frames[0]["type"] == "mark_update"
    assert frames[0]["payload"]["slug"] == "foo"
    # 50 ticks, last is 0.50 + 49*0.001 = 0.549
    assert abs(frames[0]["payload"]["mark"] - 0.549) < 1e-6


def test_multi_slug_burst_one_event_per_slug():
    bus = EventBus()
    q = bus.subscribe()
    tap = MarketTap(bus=bus, interval_sec=0.2)

    tap.feed({
        "foo": {"current_price": 0.5},
        "bar": {"current_price": 0.7},
        "baz": {"current_price": 0.9},
    })
    tap.flush_if_due()
    slugs = set()
    while not q.empty():
        slugs.add(q.get_nowait()["payload"]["slug"])
    assert slugs == {"foo", "bar", "baz"}


def test_no_emission_when_price_unchanged():
    bus = EventBus()
    q = bus.subscribe()
    tap = MarketTap(bus=bus, interval_sec=0.2)

    tap.feed({"foo": {"current_price": 0.5}})
    tap.flush_if_due()
    # drain
    while not q.empty():
        q.get_nowait()

    # Same price again — no new emission.
    tap.feed({"foo": {"current_price": 0.5}})
    time.sleep(0.25)
    tap.flush_if_due()
    assert q.empty()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && python -m pytest tests/dugout_dash/test_market_tap_coalesce.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement MarketTap**

Create `sports_bot_v2/dugout_dash/market_tap.py`:
```python
"""Polls GLOBAL_STATE_HUB marks and emits coalesced mark_update events.

Coalescing: for any slug whose price moved since last emission, emit at
most one mark_update per coalesce-interval. Protects the browser from
CLOB burst traffic.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

from dugout_dash.events import EventBus, GLOBAL_EVENT_BUS

logger = logging.getLogger("dugout.market_tap")


class MarketTap:
    def __init__(self, bus: EventBus | None = None, interval_sec: float = 0.2) -> None:
        self.bus = bus or GLOBAL_EVENT_BUS
        self.interval = interval_sec
        self._last_emitted: dict[str, float] = {}   # slug -> last-emitted mark
        self._pending: dict[str, float] = {}         # slug -> latest mark awaiting flush
        self._last_flush = 0.0
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def feed(self, marks: dict[str, dict[str, Any]]) -> None:
        """marks: {slug: {current_price, best_bid, best_ask, ...}}"""
        for slug, row in marks.items():
            px = row.get("current_price")
            if px is None:
                continue
            self._pending[slug] = float(px)

    def flush_if_due(self, now: float | None = None) -> None:
        now = now if now is not None else time.monotonic()
        if now - self._last_flush < self.interval:
            return
        self._last_flush = now
        for slug, mark in list(self._pending.items()):
            prev = self._last_emitted.get(slug)
            if prev is not None and abs(mark - prev) < 1e-9:
                continue
            self.bus.publish("mark_update", {
                "slug": slug,
                "mark": mark,
                "prev_mark": prev,
                "ts": time.time(),
            })
            self._last_emitted[slug] = mark
        self._pending.clear()

    # -- background loop (production use) ------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="dugout-market-tap", daemon=True)
        self._thread.start()
        logger.info("market_tap thread started (interval=%.2fs)", self.interval)

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        # Local import so module load doesn't pay for core.state_hub cost.
        from core.state_hub import GLOBAL_STATE_HUB
        while not self._stop.is_set():
            try:
                snap = GLOBAL_STATE_HUB.snapshot()
                self.feed(snap)
                self.flush_if_due()
            except Exception as e:
                logger.warning("market_tap loop error: %s", e)
            time.sleep(min(self.interval / 2, 0.1))


GLOBAL_MARKET_TAP = MarketTap()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && python -m pytest tests/dugout_dash/test_market_tap_coalesce.py -v
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add dugout_dash/market_tap.py tests/dugout_dash/test_market_tap_coalesce.py && git commit -m "feat(dugout_dash): market_tap with 5Hz per-slug coalescing"
```

---

### Task 10: Start market_tap on app startup

**Files:**
- Modify: `sports_bot_v2/dugout_dash/__init__.py`

- [ ] **Step 1: Start the tap in create_app**

Edit `sports_bot_v2/dugout_dash/__init__.py`. Replace the existing `create_app` function with:
```python
def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["JSON_SORT_KEYS"] = False

    @app.context_processor
    def inject_globals():
        return {
            "PORT": cfg.PORT,
            "DB_PATH": cfg.DB_PATH,
            "BOT_VERSION": "0.4.2",
            "BANKROLL": cfg.STARTING_BANKROLL,
            "TODAY_PNL": 0.0,
            "LIVE_COUNT": 0,
            "OPEN_COUNT": 0,
        }

    app.register_blueprint(game_bp.bp)
    app.register_blueprint(api_bp.bp)

    # Start background market_tap subscriber once.
    if not app.config.get("TESTING"):
        from dugout_dash.market_tap import GLOBAL_MARKET_TAP
        GLOBAL_MARKET_TAP.start()

    @app.route("/healthz")
    def healthz():
        return {"ok": True, "app": "dugout_dash"}

    return app
```

- [ ] **Step 2: Smoke test — app still starts**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && DUGOUT_DASH_PORT=8901 python -m dugout_dash.run &
sleep 3
curl -s http://127.0.0.1:8901/healthz
pkill -f dugout_dash.run 2>/dev/null || true
```

Expected: `{"ok": true, "app": "dugout_dash"}` and log line `market_tap thread started`.

- [ ] **Step 3: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add dugout_dash/__init__.py && git commit -m "feat(dugout_dash): start market_tap background thread on app boot"
```

---

## Phase 2 — TRADES + TAPE pages (Tasks 11–18)

### Task 11: Open-positions reader (from state_hub + db)

**Files:**
- Create: `sports_bot_v2/dugout_dash/positions.py`

- [ ] **Step 1: Implement positions reader**

Create `sports_bot_v2/dugout_dash/positions.py`:
```python
"""Reads open positions + computes live P&L for templates."""
from __future__ import annotations

import sqlite3
from typing import Any

from dugout_dash import config as cfg


def fetch_open_positions() -> list[dict[str, Any]]:
    """Return a list of open trade dicts, each enriched with a live mark (if known)."""
    with sqlite3.connect(cfg.DB_PATH, timeout=2.0) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, ts_open, market_slug, market_id, side, qty, entry_px, fees_usd,"
            " confidence, mode, sport FROM trades WHERE status='open' ORDER BY ts_open DESC"
        ).fetchall()
    out: list[dict[str, Any]] = []
    # Enrich with live marks
    try:
        from core.state_hub import GLOBAL_STATE_HUB
        snap = GLOBAL_STATE_HUB.snapshot()
    except Exception:
        snap = {}
    for r in rows:
        d = dict(r)
        mark_row = snap.get(d["market_slug"]) or {}
        mark = mark_row.get("current_price")
        entry = float(d["entry_px"] or 0.0)
        qty = float(d["qty"] or 0.0)
        pnl = ((mark - entry) * qty) if mark is not None else None
        d["mark"] = mark
        d["pnl_usd"] = pnl
        d["pnl_pct"] = (pnl / (entry * qty) * 100.0) if (pnl is not None and entry > 0 and qty > 0) else None
        out.append(d)
    return out


def fetch_closed_today() -> list[dict[str, Any]]:
    """Closed trades in the last 24 h."""
    with sqlite3.connect(cfg.DB_PATH, timeout=2.0) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, ts_open, ts_close, market_slug, side, qty, entry_px, exit_px,"
            " pnl_usd, reason_close FROM trades"
            " WHERE status='closed' AND ts_close >= datetime('now', '-1 day')"
            " ORDER BY ts_close DESC"
        ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 2: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add dugout_dash/positions.py && git commit -m "feat(dugout_dash): positions.py reads open + closed-today trades with live marks"
```

---

### Task 12: Trade row partial + Trades blueprint

**Files:**
- Create: `sports_bot_v2/dugout_dash/templates/partials/trade_row.html`
- Create: `sports_bot_v2/dugout_dash/blueprints/trades.py`
- Create: `sports_bot_v2/dugout_dash/templates/trades.html`
- Modify: `sports_bot_v2/dugout_dash/__init__.py`

- [ ] **Step 1: Write trade_row partial**

Create `sports_bot_v2/dugout_dash/templates/partials/trade_row.html`:
```html
{# One open-position row. Used on TRADES, TAPE, and GAME detail. #}
<tr class="trade-row"
    data-trade-id="{{ p.id }}"
    data-slug="{{ p.market_slug }}"
    data-entry="{{ p.entry_px }}"
    data-qty="{{ p.qty }}"
    data-side="{{ p.side }}">
  <td class="slug">{{ p.market_slug }}</td>
  <td>{{ p.side }}</td>
  <td>{{ '%.4f'|format(p.entry_px or 0) }}</td>
  <td>{{ '%.4f'|format(p.qty or 0) }}</td>
  <td class="mark-cell">
    {% if p.mark is not none %}{{ '%.4f'|format(p.mark) }}{% else %}—{% endif %}
  </td>
  <td class="pnl-cell {% if p.pnl_usd is not none and p.pnl_usd >= 0 %}pnl-up{% elif p.pnl_usd is not none %}pnl-down{% endif %}">
    {% if p.pnl_usd is not none %}
      {% if p.pnl_usd >= 0 %}+${{ '%.2f'|format(p.pnl_usd) }}{% else %}-${{ '%.2f'|format(-p.pnl_usd) }}{% endif %}
    {% else %}—{% endif %}
  </td>
  <td class="pnl-pct">
    {% if p.pnl_pct is not none %}{{ '%.1f'|format(p.pnl_pct) }}%{% else %}—{% endif %}
  </td>
  <td>{{ p.mode or '' }}</td>
</tr>
```

- [ ] **Step 2: Write trades blueprint**

Create `sports_bot_v2/dugout_dash/blueprints/trades.py`:
```python
"""TRADES page — open positions + closed today."""
from __future__ import annotations
from flask import Blueprint, render_template

from dugout_dash.positions import fetch_open_positions, fetch_closed_today

bp = Blueprint("trades", __name__)


@bp.route("/trades")
def index():
    open_ps = fetch_open_positions()
    closed = fetch_closed_today()
    return render_template(
        "trades.html",
        ACTIVE="trades",
        OPEN_POSITIONS=open_ps,
        CLOSED_TODAY=closed,
        OPEN_COUNT=len(open_ps),
    )
```

- [ ] **Step 3: Write trades.html**

Create `sports_bot_v2/dugout_dash/templates/trades.html`:
```html
{% extends "base.html" %}
{% block title %}TRADES · Dugout Dash{% endblock %}
{% block content %}
<section class="pane">

  <div class="panel" style="margin-bottom: 16px;">
    <h3>── OPEN POSITIONS ({{ OPEN_POSITIONS|length }}) ──</h3>
    {% if OPEN_POSITIONS %}
    <table id="open-positions">
      <thead>
        <tr><th>SLUG</th><th>SIDE</th><th>ENTRY</th><th>QTY</th><th>MARK</th><th>P&amp;L</th><th>%</th><th>MODE</th></tr>
      </thead>
      <tbody>
        {% for p in OPEN_POSITIONS %}
          {% include "partials/trade_row.html" %}
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <p style="font-family: var(--font-pixel-text); font-size: 20px; color: var(--chalk-dim);">No open positions.</p>
    {% endif %}
  </div>

  <div class="panel">
    <h3>── CLOSED TODAY ({{ CLOSED_TODAY|length }}) ──</h3>
    {% if CLOSED_TODAY %}
    <table>
      <thead>
        <tr><th>CLOSED</th><th>SLUG</th><th>SIDE</th><th>ENTRY</th><th>EXIT</th><th>NET P&amp;L</th><th>REASON</th></tr>
      </thead>
      <tbody>
        {% for c in CLOSED_TODAY %}
        <tr>
          <td>{{ c.ts_close[-8:] if c.ts_close else '' }}</td>
          <td>{{ c.market_slug }}</td>
          <td>{{ c.side }}</td>
          <td>{{ '%.4f'|format(c.entry_px or 0) }}</td>
          <td>{{ '%.4f'|format(c.exit_px or 0) }}</td>
          <td class="{% if (c.pnl_usd or 0) >= 0 %}pnl-up{% else %}pnl-down{% endif %}">
            {% if (c.pnl_usd or 0) >= 0 %}+${{ '%.2f'|format(c.pnl_usd or 0) }}{% else %}-${{ '%.2f'|format(-(c.pnl_usd or 0)) }}{% endif %}
          </td>
          <td>{{ c.reason_close or '' }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <p style="font-family: var(--font-pixel-text); font-size: 20px; color: var(--chalk-dim);">No closed trades today.</p>
    {% endif %}
  </div>

</section>
{% endblock %}
```

- [ ] **Step 4: Register blueprint**

Edit `dugout_dash/__init__.py` — add:
```python
from dugout_dash.blueprints import trades as trades_bp
# ...
app.register_blueprint(trades_bp.bp)
```

- [ ] **Step 5: Smoke test**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && DUGOUT_DASH_PORT=8901 python -m dugout_dash.run &
sleep 2
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8901/trades
pkill -f dugout_dash.run 2>/dev/null || true
```

Expected: `200`.

- [ ] **Step 6: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add dugout_dash/templates/partials/trade_row.html dugout_dash/blueprints/trades.py dugout_dash/templates/trades.html dugout_dash/__init__.py && git commit -m "feat(dugout_dash): TRADES page with open positions + closed today"
```

---

### Task 13: JSON endpoints for trades + tape

**Files:**
- Modify: `sports_bot_v2/dugout_dash/blueprints/api.py`

- [ ] **Step 1: Add JSON endpoints**

Append to `sports_bot_v2/dugout_dash/blueprints/api.py`:
```python
from flask import jsonify
from dugout_dash.positions import fetch_open_positions, fetch_closed_today


@bp.route("/trades.json")
def trades_json():
    return jsonify({
        "open": fetch_open_positions(),
        "closed_today": fetch_closed_today(),
    })


@bp.route("/tape.json")
def tape_json():
    """All currently-tracked markets + last mark, for TAPE ticker strip."""
    try:
        from core.state_hub import GLOBAL_STATE_HUB
        snap = GLOBAL_STATE_HUB.snapshot()
    except Exception:
        snap = {}
    cells = []
    for slug, row in snap.items():
        cells.append({
            "slug": slug,
            "mark": row.get("current_price"),
            "best_bid": row.get("best_bid"),
            "best_ask": row.get("best_ask"),
            "stale": row.get("stale", False),
        })
    return jsonify({"cells": cells})
```

- [ ] **Step 2: Smoke test**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && DUGOUT_DASH_PORT=8901 python -m dugout_dash.run &
sleep 2
curl -s http://127.0.0.1:8901/api/trades.json | head -c 300
curl -s http://127.0.0.1:8901/api/tape.json | head -c 300
pkill -f dugout_dash.run 2>/dev/null || true
```

Expected: JSON with `open`, `closed_today`, and `cells` keys.

- [ ] **Step 3: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add dugout_dash/blueprints/api.py && git commit -m "feat(dugout_dash): /api/trades.json + /api/tape.json"
```

---

### Task 14: TAPE page — ticker marquee + position rows

**Files:**
- Create: `sports_bot_v2/dugout_dash/blueprints/tape.py`
- Create: `sports_bot_v2/dugout_dash/templates/tape.html`
- Create: `sports_bot_v2/dugout_dash/templates/partials/ticker_cell.html`
- Modify: `sports_bot_v2/dugout_dash/__init__.py`

- [ ] **Step 1: Write ticker_cell partial**

Create `sports_bot_v2/dugout_dash/templates/partials/ticker_cell.html`:
```html
<span class="ticker-cell" data-slug="{{ c.slug }}" data-mark="{{ c.mark if c.mark is not none else '' }}">
  <span class="ticker-slug">{{ c.slug[:18] }}</span>
  <span class="ticker-mark">{% if c.mark is not none %}{{ '%.2f'|format(c.mark*100) }}¢{% else %}—{% endif %}</span>
  <span class="ticker-dir"></span>
</span>
```

- [ ] **Step 2: Write tape blueprint**

Create `sports_bot_v2/dugout_dash/blueprints/tape.py`:
```python
"""TAPE page — NYSE-style marquee + position-focused wide rows with sparklines."""
from __future__ import annotations
from flask import Blueprint, render_template

from dugout_dash.positions import fetch_open_positions

bp = Blueprint("tape", __name__)


@bp.route("/tape")
def index():
    open_ps = fetch_open_positions()
    try:
        from core.state_hub import GLOBAL_STATE_HUB
        snap = GLOBAL_STATE_HUB.snapshot()
    except Exception:
        snap = {}
    cells = [
        {
            "slug": slug,
            "mark": row.get("current_price"),
            "stale": row.get("stale", False),
        }
        for slug, row in snap.items()
    ]
    return render_template(
        "tape.html",
        ACTIVE="tape",
        CELLS=cells,
        OPEN_POSITIONS=open_ps,
        OPEN_COUNT=len(open_ps),
    )
```

- [ ] **Step 3: Write tape.html**

Create `sports_bot_v2/dugout_dash/templates/tape.html`:
```html
{% extends "base.html" %}
{% block title %}TAPE · Dugout Dash{% endblock %}
{% block content %}

<div class="tape-marquee">
  <div class="tape-track" id="tape-track">
    {# Render cells twice so the scroll loops seamlessly. #}
    {% for c in CELLS %}{% include "partials/ticker_cell.html" %}{% endfor %}
    {% for c in CELLS %}{% include "partials/ticker_cell.html" %}{% endfor %}
  </div>
</div>

<section class="pane">
  <div class="panel">
    <h3>── POSITIONS · REALTIME ──</h3>
    {% if OPEN_POSITIONS %}
    <table id="tape-rows">
      <thead>
        <tr><th>SLUG</th><th>SIDE</th><th>ENTRY</th><th>MARK</th><th>P&amp;L</th><th>%</th><th>60s</th></tr>
      </thead>
      <tbody>
        {% for p in OPEN_POSITIONS %}
        <tr class="trade-row"
            data-trade-id="{{ p.id }}"
            data-slug="{{ p.market_slug }}"
            data-entry="{{ p.entry_px }}"
            data-qty="{{ p.qty }}"
            data-side="{{ p.side }}">
          <td>{{ p.market_slug }}</td>
          <td>{{ p.side }}</td>
          <td>{{ '%.4f'|format(p.entry_px or 0) }}</td>
          <td class="mark-cell">{% if p.mark is not none %}{{ '%.4f'|format(p.mark) }}{% else %}—{% endif %}</td>
          <td class="pnl-cell {% if p.pnl_usd is not none and p.pnl_usd >= 0 %}pnl-up{% elif p.pnl_usd is not none %}pnl-down{% endif %}">
            {% if p.pnl_usd is not none %}{% if p.pnl_usd >= 0 %}+${{ '%.2f'|format(p.pnl_usd) }}{% else %}-${{ '%.2f'|format(-p.pnl_usd) }}{% endif %}{% else %}—{% endif %}
          </td>
          <td class="pnl-pct">{% if p.pnl_pct is not none %}{{ '%.1f'|format(p.pnl_pct) }}%{% else %}—{% endif %}</td>
          <td><svg class="sparkline" data-slug="{{ p.market_slug }}"></svg></td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <p style="font-family: var(--font-pixel-text); font-size: 20px; color: var(--chalk-dim);">No open positions to tape.</p>
    {% endif %}
  </div>
</section>
{% endblock %}
```

- [ ] **Step 4: Register blueprint**

Edit `dugout_dash/__init__.py`:
```python
from dugout_dash.blueprints import tape as tape_bp
# ...
app.register_blueprint(tape_bp.bp)
```

- [ ] **Step 5: Smoke test**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && DUGOUT_DASH_PORT=8901 python -m dugout_dash.run &
sleep 2
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8901/tape
pkill -f dugout_dash.run 2>/dev/null || true
```

Expected: `200`.

- [ ] **Step 6: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add dugout_dash/blueprints/tape.py dugout_dash/templates/tape.html dugout_dash/templates/partials/ticker_cell.html dugout_dash/__init__.py && git commit -m "feat(dugout_dash): TAPE page with marquee ticker + position rows"
```

---

### Task 15: Download CC0 sound assets

**Files:**
- Create: `sports_bot_v2/dugout_dash/static/sounds/base_hit.wav`
- Create: `sports_bot_v2/dugout_dash/static/sounds/strikeout.wav`
- Create: `sports_bot_v2/dugout_dash/static/sounds/walkoff.wav`
- Create: `sports_bot_v2/dugout_dash/static/sounds/foul.wav`

- [ ] **Step 1: Create sounds directory**

```bash
mkdir -p /c/Users/johnny/Desktop/sports_bot_v2/dugout_dash/static/sounds
```

- [ ] **Step 2: Generate 8-bit WAVs in pure Python (no external deps)**

Create a one-off script `sports_bot_v2/scripts/gen_sounds.py`:
```python
"""Generate tiny 8-bit-style SFX as CC0 placeholders. Run once."""
import math
import struct
import wave
from pathlib import Path

RATE = 22050  # classic 8-bit sample rate
OUT = Path(__file__).resolve().parent.parent / "dugout_dash" / "static" / "sounds"
OUT.mkdir(parents=True, exist_ok=True)


def square(freq: float, dur: float, vol: float = 0.4) -> bytes:
    n = int(RATE * dur)
    frames = bytearray()
    for i in range(n):
        t = i / RATE
        v = vol if math.sin(2 * math.pi * freq * t) > 0 else -vol
        # Simple linear decay to avoid clicks at end.
        env = max(0.0, 1.0 - i / n)
        sample = int(v * env * 32767)
        frames += struct.pack("<h", sample)
    return bytes(frames)


def write(name: str, data: bytes) -> None:
    with wave.open(str(OUT / name), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(data)


def main():
    # base_hit: rising 3-note blip
    write("base_hit.wav", square(523, 0.08) + square(659, 0.08) + square(784, 0.12))
    # strikeout: descending 2-note
    write("strikeout.wav", square(440, 0.10) + square(220, 0.18))
    # walkoff: triumphant 4-note
    write("walkoff.wav", square(523, 0.08) + square(659, 0.08) + square(784, 0.08) + square(1046, 0.20))
    # foul: brief buzz
    write("foul.wav", square(200, 0.12))
    print("generated", [p.name for p in OUT.glob("*.wav")])


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run it**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && mkdir -p scripts && python scripts/gen_sounds.py
ls dugout_dash/static/sounds/
```

Expected: 4 `.wav` files listed.

- [ ] **Step 4: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add scripts/gen_sounds.py dugout_dash/static/sounds/*.wav && git commit -m "chore(dugout_dash): procedurally generated 8-bit SFX (CC0)"
```

---

### Task 16: Dugout.js — SSE client + toast + notifications + sounds

**Files:**
- Modify: `sports_bot_v2/dugout_dash/static/dugout.js`

- [ ] **Step 1: Replace stub with full client**

Overwrite `sports_bot_v2/dugout_dash/static/dugout.js`:
```js
// dugout.js — SSE client, toast, notifications, sounds, P&L recomputation.
(function () {
  'use strict';

  // ---------- Toast ------------------------------------------------------

  function toast(title, body, ok) {
    const root = document.getElementById('toast-root');
    if (!root) return;
    const el = document.createElement('div');
    el.className = 'toast' + (ok === false ? ' err' : '');
    el.innerHTML =
      '<div class="title">' + title + '</div>' +
      (body ? '<div>' + body + '</div>' : '');
    root.appendChild(el);
    setTimeout(() => el.classList.add('show'), 10);
    setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 300); }, 4000);
  }

  // ---------- Browser Notification --------------------------------------

  function ensureNotifyPermission() {
    if (!('Notification' in window)) return;
    if (Notification.permission === 'default') {
      // One-time prompt on first user interaction to avoid auto-block.
      document.addEventListener('click', () => {
        if (Notification.permission === 'default') Notification.requestPermission();
      }, { once: true });
    }
  }

  function notify(title, body) {
    if ('Notification' in window && Notification.permission === 'granted') {
      try { new Notification(title, { body }); } catch (e) { /* ignore */ }
    }
  }

  // ---------- Sound -----------------------------------------------------

  const soundCache = {};
  function playSound(name) {
    try {
      if (!soundCache[name]) {
        soundCache[name] = new Audio('/static/sounds/' + name + '.wav');
        soundCache[name].volume = 0.5;
      }
      soundCache[name].currentTime = 0;
      soundCache[name].play().catch(() => {}); // autoplay policy — ignore
    } catch (e) { /* ignore */ }
  }

  // ---------- SSE -------------------------------------------------------

  let es = null;
  let reconnectAt = null;

  function setSSEChip(state) {
    const chip = document.getElementById('sse-chip');
    if (!chip) return;
    if (state === 'ok') { chip.className = 'chip-pixel chip-pixel--ok'; chip.textContent = '✓ LIVE'; }
    else if (state === 'stale') { chip.className = 'chip-pixel chip-pixel--warn chip-stale'; chip.textContent = '⚠ STALE'; }
  }

  function connectSSE() {
    if (es) { try { es.close(); } catch (e) {} }
    es = new EventSource('/api/events');

    es.addEventListener('hello', () => setSSEChip('ok'));
    es.addEventListener('trade_entered', (e) => onTradeEntered(JSON.parse(e.data)));
    es.addEventListener('trade_exited',  (e) => onTradeExited(JSON.parse(e.data)));
    es.addEventListener('mark_update',   (e) => onMarkUpdate(JSON.parse(e.data)));

    es.onerror = () => {
      setSSEChip('stale');
      try { es.close(); } catch (e) {}
      if (!reconnectAt) playSound('foul');
      reconnectAt = setTimeout(() => { reconnectAt = null; connectSSE(); }, 3000);
    };
  }

  // ---------- Handlers --------------------------------------------------

  function onTradeEntered(p) {
    const title = '⚾ BASE HIT — TRADE FILLED';
    const body = p.side + ' · ' + p.slug + ' @ ' + Number(p.entry_px).toFixed(4) + ' · $' + Number(p.size_usd).toFixed(2);
    toast(title, body, true);
    notify(title, body);
    playSound('base_hit');
    // Future task: prepend row to #open-positions (Task 18).
    if (window.dugoutOnTradeEntered) window.dugoutOnTradeEntered(p);
  }

  function onTradeExited(p) {
    const winning = (p.net_pnl || 0) >= 0;
    const title = winning ? '🏆 WALK-OFF — TRADE CLOSED' : '❌ STRIKEOUT — TRADE CLOSED';
    const pnlStr = (p.net_pnl >= 0 ? '+$' : '-$') + Math.abs(p.net_pnl || 0).toFixed(2);
    const body = p.slug + ' · ' + p.reason + ' · ' + pnlStr;
    toast(title, body, winning);
    notify(title, body);
    playSound(winning ? 'walkoff' : 'strikeout');
    if (window.dugoutOnTradeExited) window.dugoutOnTradeExited(p);
  }

  function onMarkUpdate(p) {
    // Update ticker cells
    document.querySelectorAll('.ticker-cell[data-slug="' + cssEscape(p.slug) + '"]').forEach((cell) => {
      const prev = parseFloat(cell.getAttribute('data-mark'));
      const markEl = cell.querySelector('.ticker-mark');
      const dirEl = cell.querySelector('.ticker-dir');
      if (markEl) markEl.textContent = (p.mark * 100).toFixed(2) + '¢';
      cell.setAttribute('data-mark', p.mark);
      if (!Number.isNaN(prev) && dirEl) {
        if (p.mark > prev) { dirEl.textContent = ' ▲'; dirEl.className = 'ticker-dir up'; }
        else if (p.mark < prev) { dirEl.textContent = ' ▼'; dirEl.className = 'ticker-dir down'; }
      }
    });
    // Update P&L rows
    document.querySelectorAll('.trade-row[data-slug="' + cssEscape(p.slug) + '"]').forEach((row) => {
      const entry = parseFloat(row.getAttribute('data-entry')) || 0;
      const qty = parseFloat(row.getAttribute('data-qty')) || 0;
      const markCell = row.querySelector('.mark-cell');
      const pnlCell = row.querySelector('.pnl-cell');
      const pctCell = row.querySelector('.pnl-pct');
      if (markCell) markCell.textContent = p.mark.toFixed(4);
      const pnl = (p.mark - entry) * qty;
      if (pnlCell) {
        pnlCell.textContent = (pnl >= 0 ? '+$' : '-$') + Math.abs(pnl).toFixed(2);
        pnlCell.classList.toggle('pnl-up', pnl >= 0);
        pnlCell.classList.toggle('pnl-down', pnl < 0);
        pnlCell.classList.remove('flash-up', 'flash-down');
        void pnlCell.offsetWidth; // restart animation
        pnlCell.classList.add(pnl >= 0 ? 'flash-up' : 'flash-down');
      }
      if (pctCell && entry > 0 && qty > 0) {
        const pct = (pnl / (entry * qty)) * 100;
        pctCell.textContent = pct.toFixed(1) + '%';
      }
    });
    if (window.dugoutOnMarkUpdate) window.dugoutOnMarkUpdate(p);
  }

  function cssEscape(s) {
    return String(s).replace(/["\\]/g, '\\$&');
  }

  // ---------- Boot ------------------------------------------------------

  ensureNotifyPermission();
  connectSSE();
})();
```

- [ ] **Step 2: Manual test — trade_entered fires the full chain**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && DUGOUT_DASH_PORT=8901 python -m dugout_dash.run &
sleep 2
```

Open `http://127.0.0.1:8901/trades` in a browser. Click once anywhere on the page (satisfies autoplay + notification prompt). Then in a second shell, publish a synthetic event:
```bash
python -c "
import time
from dugout_dash.events import GLOBAL_EVENT_BUS
GLOBAL_EVENT_BUS.publish('trade_entered', {
    'trade_id': 99, 'slug': 'test-market', 'side': 'BUY_YES',
    'entry_px': 0.48, 'qty': 208.33, 'size_usd': 100.0,
    'confidence': 0.72, 'mode': 'neutral', 'ts': time.strftime('%FT%T')
})
time.sleep(1)
"
```

Wait — this spawns a **different** Python process, so its EventBus is a different instance. That won't reach the browser. Instead, use `curl` against a test endpoint OR use the bot's own event bus. Run the synthetic via the running app process:
```bash
curl -s -X POST http://127.0.0.1:8901/api/events/test_publish -H 'Content-Type: application/json' -d '{"type":"trade_entered","payload":{"trade_id":99,"slug":"test","side":"BUY_YES","entry_px":0.48,"qty":208.33,"size_usd":100}}'
```

Wait — we haven't added that endpoint. Add it now (dev-only, guarded by env):

Append to `dugout_dash/blueprints/api.py`:
```python
import os as _os
from flask import request


@bp.route("/events/test_publish", methods=["POST"])
def events_test_publish():
    if _os.getenv("DUGOUT_DASH_DEV", "0") != "1":
        return {"error": "dev-only"}, 403
    body = request.get_json(force=True, silent=True) or {}
    GLOBAL_EVENT_BUS.publish(body.get("type", "x"), body.get("payload", {}))
    return {"ok": True}
```

Restart with `DUGOUT_DASH_DEV=1`:
```bash
pkill -f dugout_dash.run 2>/dev/null || true
DUGOUT_DASH_PORT=8901 DUGOUT_DASH_DEV=1 python -m dugout_dash.run &
sleep 2
```

Re-open the browser, interact once, then:
```bash
curl -s -X POST http://127.0.0.1:8901/api/events/test_publish -H 'Content-Type: application/json' -d '{"type":"trade_entered","payload":{"trade_id":99,"slug":"test","side":"BUY_YES","entry_px":0.48,"qty":208.33,"size_usd":100}}'
```

Expected: toast appears in the browser, OS notification pops (if permission granted), `base_hit.wav` plays.

Kill:
```bash
pkill -f dugout_dash.run 2>/dev/null || true
```

- [ ] **Step 3: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add dugout_dash/static/dugout.js dugout_dash/blueprints/api.py && git commit -m "feat(dugout_dash): full SSE client — toast, OS notify, sounds, P&L flash"
```

---

### Task 17: SSE-driven row insertion + removal

**Files:**
- Modify: `sports_bot_v2/dugout_dash/static/dugout.js`
- Modify: `sports_bot_v2/dugout_dash/templates/trades.html`

- [ ] **Step 1: Expose page-level hook in trades.html**

Edit `dugout_dash/templates/trades.html` — before `{% endblock %}`, append:
```html
{% block scripts %}
<script>
window.dugoutOnTradeEntered = function (p) {
  const tbody = document.querySelector('#open-positions tbody');
  if (!tbody) { location.reload(); return; }
  const tr = document.createElement('tr');
  tr.className = 'trade-row flash-up';
  tr.setAttribute('data-trade-id', p.trade_id);
  tr.setAttribute('data-slug', p.slug);
  tr.setAttribute('data-entry', p.entry_px);
  tr.setAttribute('data-qty', p.qty);
  tr.setAttribute('data-side', p.side);
  tr.innerHTML =
    '<td>' + p.slug + '</td>' +
    '<td>' + p.side + '</td>' +
    '<td>' + Number(p.entry_px).toFixed(4) + '</td>' +
    '<td>' + Number(p.qty).toFixed(4) + '</td>' +
    '<td class="mark-cell">—</td>' +
    '<td class="pnl-cell">—</td>' +
    '<td class="pnl-pct">—</td>' +
    '<td>' + (p.mode || '') + '</td>';
  tbody.insertBefore(tr, tbody.firstChild);
};

window.dugoutOnTradeExited = function (p) {
  const row = document.querySelector('.trade-row[data-trade-id="' + p.trade_id + '"]');
  if (row) { row.classList.add('flash-down'); setTimeout(() => row.remove(), 500); }
};
</script>
{% endblock %}
```

- [ ] **Step 2: Manual test — verify prepend + remove**

Start in dev mode and open `/trades`, then:
```bash
curl -s -X POST http://127.0.0.1:8901/api/events/test_publish -H 'Content-Type: application/json' -d '{"type":"trade_entered","payload":{"trade_id":101,"slug":"synth-A","side":"BUY_YES","entry_px":0.48,"qty":200,"size_usd":96,"mode":"neutral"}}'
curl -s -X POST http://127.0.0.1:8901/api/events/test_publish -H 'Content-Type: application/json' -d '{"type":"trade_exited","payload":{"trade_id":101,"slug":"synth-A","side":"BUY_YES","entry_px":0.48,"exit_px":0.55,"net_pnl":14.0,"reason":"TAKE_PROFIT"}}'
```

Expected: row appears with flash, then removes with flash.

- [ ] **Step 3: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add dugout_dash/templates/trades.html && git commit -m "feat(dugout_dash): SSE-driven row insertion + removal on TRADES"
```

---

### Task 18: Sparkline (60s circular buffer) on TAPE rows

**Files:**
- Modify: `sports_bot_v2/dugout_dash/templates/tape.html`

- [ ] **Step 1: Append sparkline JS to tape.html**

Edit `dugout_dash/templates/tape.html` — append before `{% endblock %}`:
```html
{% block scripts %}
<script>
const sparkBufs = new Map();  // slug -> [60 numbers or nulls]
const SPARK_W = 240, SPARK_H = 40;

function ensureBuf(slug) {
  if (!sparkBufs.has(slug)) sparkBufs.set(slug, new Array(60).fill(null));
  return sparkBufs.get(slug);
}

function pushTick(slug, mark) {
  const buf = ensureBuf(slug);
  buf.shift(); buf.push(mark);
  renderSpark(slug, buf);
}

function renderSpark(slug, buf) {
  const svg = document.querySelector('.sparkline[data-slug="' + slug.replace(/["\\]/g,'\\$&') + '"]');
  if (!svg) return;
  const vals = buf.filter(v => v !== null);
  if (vals.length < 2) { svg.innerHTML = ''; return; }
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const span = (hi - lo) || 1e-6;
  svg.setAttribute('viewBox', `0 0 ${SPARK_W} ${SPARK_H}`);
  const barW = SPARK_W / 60;
  let bars = '';
  buf.forEach((v, i) => {
    if (v === null) return;
    const h = ((v - lo) / span) * (SPARK_H - 4) + 2;
    const x = i * barW;
    const y = SPARK_H - h;
    const color = (i > 0 && buf[i-1] !== null && v < buf[i-1]) ? 'var(--foul-red)' : 'var(--scoreboard-green)';
    bars += `<rect x="${x}" y="${y}" width="${Math.max(1,barW-1)}" height="${h}" fill="${color}"/>`;
  });
  svg.innerHTML = bars;
}

window.dugoutOnMarkUpdate = function (p) {
  pushTick(p.slug, p.mark);
};

// 1 Hz "heartbeat push" so sparkline evolves even on quiet slugs.
setInterval(() => {
  sparkBufs.forEach((buf, slug) => {
    const last = buf[buf.length - 1];
    if (last !== null) { buf.shift(); buf.push(last); renderSpark(slug, buf); }
  });
}, 1000);

// Seed from current marks on page load.
fetch('/api/tape.json').then(r => r.json()).then(j => {
  (j.cells || []).forEach(c => { if (c.mark !== null && c.mark !== undefined) pushTick(c.slug, c.mark); });
});
</script>
{% endblock %}
```

- [ ] **Step 2: Manual test**

```bash
DUGOUT_DASH_PORT=8901 DUGOUT_DASH_DEV=1 python -m dugout_dash.run &
sleep 2
```

Open `/tape`; fire ~20 synthetic `mark_update`s at varying prices:
```bash
for v in 0.50 0.51 0.52 0.49 0.55 0.58 0.60 0.57 0.53 0.50; do
  curl -s -X POST http://127.0.0.1:8901/api/events/test_publish -H 'Content-Type: application/json' -d "{\"type\":\"mark_update\",\"payload\":{\"slug\":\"synth-A\",\"mark\":$v}}"
  sleep 0.3
done
pkill -f dugout_dash.run 2>/dev/null || true
```

Expected: sparkline animates bar-by-bar (only visible if a row for `synth-A` exists — seed it via a prior `trade_entered` or check existing positions).

- [ ] **Step 3: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add dugout_dash/templates/tape.html && git commit -m "feat(dugout_dash): 60s sparkline buffer + SVG render on TAPE rows"
```

---

## Phase 3 — GAME page (Tasks 19–23)

### Task 19: Extract espn_cache module

**Files:**
- Create: `sports_bot_v2/core/espn_cache.py`

- [ ] **Step 1: Identify the ESPN logic in dashboard_server.py**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && sed -n '79,200p' dashboard_server.py
```

This includes `_espn_lock`, `_espn_scoreboard`, `_espn_detail`, `ESPN_SB_URL`, `ESPN_DETAIL_URL`, `_http_get`, `_build_games_from_raw`, and the polling loop.

- [ ] **Step 2: Create core/espn_cache.py**

Create `sports_bot_v2/core/espn_cache.py`:
```python
"""Centralized ESPN MLB scoreboard + detail cache.

Owns the HTTP polling, in-memory caches, and freshness timestamps.
Dashboard servers (dugout_dash, legacy) consume via get_scoreboard()
and get_detail(espn_id).
"""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request
from typing import Any

logger = logging.getLogger("core.espn_cache")

ESPN_SB_URL = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"
ESPN_DETAIL_URL = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/summary?event={}"

_lock = threading.Lock()
_scoreboard: dict[str, Any] = {"games": [], "fetched_at": None, "error": None}
_detail: dict[str, dict] = {}
_poll_thread: threading.Thread | None = None
_stop = threading.Event()


def _http_get(url: str, timeout: int = 8) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "dugout-dash/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _build_games_from_raw(raw: dict) -> list[dict]:
    games: list[dict] = []
    for event in raw.get("events", []):
        espn_id = str(event.get("id", ""))
        comp = (event.get("competitions") or [{}])[0]
        competitors = comp.get("competitors") or []
        home = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away = next((c for c in competitors if c.get("homeAway") == "away"), {})
        status_obj = comp.get("status") or {}
        status_type = status_obj.get("type") or {}
        sb_sit = comp.get("situation") or {}
        games.append({
            "espn_id": espn_id,
            "home": (home.get("team") or {}).get("displayName", "?"),
            "away": (away.get("team") or {}).get("displayName", "?"),
            "home_abbr": (home.get("team") or {}).get("abbreviation", ""),
            "away_abbr": (away.get("team") or {}).get("abbreviation", ""),
            "home_score": int(home.get("score", 0) or 0),
            "away_score": int(away.get("score", 0) or 0),
            "inning": int(status_obj.get("period") or 0),
            "inning_half": "bottom" if sb_sit.get("isTopInning") is False else "top",
            "status": status_type.get("name", "STATUS_UNKNOWN"),
            "status_display": status_type.get("shortDetail", ""),
            "outs": sb_sit.get("outs"),
            "balls": sb_sit.get("balls"),
            "strikes": sb_sit.get("strikes"),
            "on_first": bool(sb_sit.get("onFirst")),
            "on_second": bool(sb_sit.get("onSecond")),
            "on_third": bool(sb_sit.get("onThird")),
        })
    return games


def get_scoreboard() -> dict:
    with _lock:
        return dict(_scoreboard)


def get_detail(espn_id: str) -> dict | None:
    with _lock:
        return _detail.get(espn_id)


def _refresh_scoreboard() -> None:
    try:
        raw = _http_get(ESPN_SB_URL)
        games = _build_games_from_raw(raw)
        with _lock:
            _scoreboard["games"] = games
            _scoreboard["fetched_at"] = time.time()
            _scoreboard["error"] = None
    except Exception as e:
        with _lock:
            _scoreboard["error"] = str(e)
        logger.warning("espn scoreboard fetch failed: %s", e)


def _refresh_detail(espn_id: str) -> None:
    try:
        raw = _http_get(ESPN_DETAIL_URL.format(espn_id))
        with _lock:
            _detail[espn_id] = {"data": raw, "fetched_at": time.time()}
    except Exception as e:
        logger.warning("espn detail fetch failed (%s): %s", espn_id, e)


def _poll_loop() -> None:
    while not _stop.is_set():
        _refresh_scoreboard()
        # refresh details for each live game
        with _lock:
            ids = [g["espn_id"] for g in _scoreboard["games"] if g["espn_id"]]
        for gid in ids[:15]:
            if _stop.is_set():
                break
            _refresh_detail(gid)
        _stop.wait(20.0)


def start() -> None:
    global _poll_thread
    if _poll_thread and _poll_thread.is_alive():
        return
    _stop.clear()
    _poll_thread = threading.Thread(target=_poll_loop, name="espn-cache", daemon=True)
    _poll_thread.start()
    logger.info("espn_cache poll thread started")


def stop() -> None:
    _stop.set()
```

- [ ] **Step 3: Start espn_cache in create_app**

Edit `dugout_dash/__init__.py` — inside the `if not app.config.get("TESTING"):` block add:
```python
from core import espn_cache
espn_cache.start()
```

- [ ] **Step 4: Smoke test**

```bash
DUGOUT_DASH_PORT=8901 python -m dugout_dash.run &
sleep 25  # let it poll once
curl -s http://127.0.0.1:8901/healthz
pkill -f dugout_dash.run 2>/dev/null || true
```

Expected log: `espn_cache poll thread started`.

- [ ] **Step 5: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add core/espn_cache.py dugout_dash/__init__.py && git commit -m "feat(core): extract espn_cache module with background poll thread"
```

---

### Task 20: Game field rail — tiles + selection

**Files:**
- Create: `sports_bot_v2/dugout_dash/templates/partials/game_tile.html`
- Modify: `sports_bot_v2/dugout_dash/blueprints/game.py`
- Modify: `sports_bot_v2/dugout_dash/templates/game.html`

- [ ] **Step 1: Write game_tile partial**

Create `sports_bot_v2/dugout_dash/templates/partials/game_tile.html`:
```html
<a href="{{ url_for('game.detail', espn_id=g.espn_id) }}"
   class="game-tile {% if g.espn_id == SELECTED %}selected{% endif %}">
  <div class="teams">{{ g.away_abbr or g.away[:3] }} @ {{ g.home_abbr or g.home[:3] }}</div>
  <div>{{ g.away_score }} – {{ g.home_score }} · <span class="state">
    {% if g.status == 'STATUS_FINAL' %}FINAL
    {% elif g.inning > 0 %}{{ 'T' if g.inning_half == 'top' else 'B' }}{{ g.inning }}
    {% else %}{{ g.status_display or g.status }}{% endif %}
  </span></div>
</a>
```

- [ ] **Step 2: Update game blueprint**

Replace `dugout_dash/blueprints/game.py`:
```python
"""GAME page blueprint — landing + per-game detail."""
from __future__ import annotations

from flask import Blueprint, render_template

from core import espn_cache
from dugout_dash import config as cfg
from dugout_dash.positions import fetch_open_positions

bp = Blueprint("game", __name__)


@bp.route("/")
def index():
    games = espn_cache.get_scoreboard().get("games", [])
    open_ps = fetch_open_positions()
    selected = _pick_default(games, open_ps)
    return render_template(
        "game.html",
        ACTIVE="game",
        GAMES=games,
        SELECTED=selected["espn_id"] if selected else None,
        SELECTED_GAME=selected,
        POSITION=_match_position(selected, open_ps),
        TAZZ_URL=_tazz_url(selected),
        TAZZ_FORCE_LINK=cfg.TAZZ_FORCE_LINK,
        LIVE_COUNT=len(games),
        OPEN_COUNT=len(open_ps),
    )


@bp.route("/game/<espn_id>")
def detail(espn_id: str):
    games = espn_cache.get_scoreboard().get("games", [])
    selected = next((g for g in games if g["espn_id"] == espn_id), None)
    open_ps = fetch_open_positions()
    return render_template(
        "game.html",
        ACTIVE="game",
        GAMES=games,
        SELECTED=espn_id,
        SELECTED_GAME=selected,
        POSITION=_match_position(selected, open_ps),
        TAZZ_URL=_tazz_url(selected),
        TAZZ_FORCE_LINK=cfg.TAZZ_FORCE_LINK,
        LIVE_COUNT=len(games),
        OPEN_COUNT=len(open_ps),
    )


def _pick_default(games, positions):
    """Select default game: the one matching the most recent open position, else first live game."""
    if positions and games:
        for p in positions:
            for g in games:
                if (g.get("home_abbr") or "").lower() in p["market_slug"].lower() \
                   or (g.get("away_abbr") or "").lower() in p["market_slug"].lower():
                    return g
    live = [g for g in games if g.get("inning", 0) > 0 and g.get("status") != "STATUS_FINAL"]
    return live[0] if live else (games[0] if games else None)


def _match_position(game, positions):
    if not game or not positions:
        return None
    for p in positions:
        if (game.get("home_abbr") or "").lower() in p["market_slug"].lower() \
           or (game.get("away_abbr") or "").lower() in p["market_slug"].lower():
            return p
    return None


def _tazz_url(game):
    if not game:
        return None
    away = (game.get("away_abbr") or "").lower()
    home = (game.get("home_abbr") or "").lower()
    if not (away and home):
        return None
    return cfg.TAZZ_BASE_URL.format(slug=f"{away}-vs-{home}")
```

- [ ] **Step 3: Update game.html**

Replace `dugout_dash/templates/game.html`:
```html
{% extends "base.html" %}
{% block title %}GAME · Dugout Dash{% endblock %}
{% block content %}
<div class="dash-shell">

  <aside class="field-rail">
    <div class="rail-title">── FIELD ──</div>
    {% if GAMES %}
      {% for g in GAMES %}{% include "partials/game_tile.html" %}{% endfor %}
    {% else %}
      <div class="rail-title" style="color: var(--chalk-dim);">no games today</div>
    {% endif %}
  </aside>

  <section class="pane">
    {% if SELECTED_GAME %}
      {% set g = SELECTED_GAME %}
      <div style="display:flex; align-items:baseline; gap:16px; border-bottom: 2px dashed var(--scoreboard-amber); padding-bottom:8px; margin-bottom:14px;">
        <div style="font-family: var(--font-pixel); font-size: 22px;">{{ g.away }} {{ g.away_score }} — {{ g.home }} {{ g.home_score }}</div>
        <div style="font-family: var(--font-pixel-text); font-size: 20px; color: var(--scoreboard-amber);">
          {% if g.status == 'STATUS_FINAL' %}FINAL
          {% elif g.inning > 0 %}{{ 'TOP' if g.inning_half == 'top' else 'BOT' }} {{ g.inning }}{% if g.outs is not none %} · {{ g.outs }} OUT{% endif %}
          {% else %}{{ g.status_display }}{% endif %}
        </div>
      </div>

      <div class="main-grid">
        <div class="tazz-panel">
          {% if TAZZ_URL and not TAZZ_FORCE_LINK %}
            <iframe id="tazz-iframe" src="{{ TAZZ_URL }}" allow="autoplay; fullscreen"></iframe>
          {% endif %}
          <div class="tazz-fallback" id="tazz-fallback" {% if TAZZ_URL and not TAZZ_FORCE_LINK %}style="display:none;"{% endif %}>
            {% if TAZZ_URL %}
              <a class="tazz-watch-btn" href="{{ TAZZ_URL }}" target="_blank" rel="noopener">▶ WATCH ON TAZZ</a>
              <div class="tazz-sub">iframe blocked · opens in a new tab</div>
            {% else %}
              <div class="tazz-sub">no tazz URL (need team abbreviations)</div>
            {% endif %}
          </div>
        </div>

        {% include "partials/pos_card.html" %}
      </div>

      <div style="margin-top:16px;">
        <div class="panel">
          <h3>── TRADE HISTORY (THIS GAME) ──</h3>
          <p style="font-family: var(--font-pixel-text); font-size:18px; color: var(--chalk-dim);">(filled in Task 21)</p>
        </div>
      </div>
    {% else %}
      <p style="font-family: var(--font-pixel-text); font-size: 22px; color: var(--chalk-dim);">No games live right now. Check back closer to first pitch.</p>
    {% endif %}
  </section>
</div>

{% block scripts %}
<script>
// Tazz iframe watchdog: if it doesn't fire load in {{ config.TAZZ_IFRAME_TIMEOUT_MS|default(3000) }} ms, swap in the fallback.
(function () {
  const ifr = document.getElementById('tazz-iframe');
  const fb = document.getElementById('tazz-fallback');
  if (!ifr || !fb) return;
  let loaded = false;
  ifr.addEventListener('load', () => { loaded = true; });
  setTimeout(() => {
    if (!loaded) { ifr.style.display = 'none'; fb.style.display = 'block'; }
  }, 3000);
})();
</script>
{% endblock %}
{% endblock %}
```

- [ ] **Step 4: Smoke test**

```bash
DUGOUT_DASH_PORT=8901 python -m dugout_dash.run &
sleep 25
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8901/
pkill -f dugout_dash.run 2>/dev/null || true
```

Expected: `200`. Open in browser — field rail should show today's games, header shows selected game score/inning.

- [ ] **Step 5: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add dugout_dash/templates/partials/game_tile.html dugout_dash/blueprints/game.py dugout_dash/templates/game.html && git commit -m "feat(dugout_dash): GAME page with field rail + tazz embed + watchdog"
```

---

### Task 21: Position card partial + game-scoped trade history

**Files:**
- Create: `sports_bot_v2/dugout_dash/templates/partials/pos_card.html`
- Modify: `sports_bot_v2/dugout_dash/templates/game.html`
- Modify: `sports_bot_v2/dugout_dash/blueprints/game.py`

- [ ] **Step 1: Write pos_card partial**

Create `sports_bot_v2/dugout_dash/templates/partials/pos_card.html`:
```html
<div class="pos-card"
     {% if POSITION %}data-slug="{{ POSITION.market_slug }}"
     data-entry="{{ POSITION.entry_px }}"
     data-qty="{{ POSITION.qty }}"
     data-side="{{ POSITION.side }}"{% endif %}>
  <h3>── POSITION ──</h3>
  {% if POSITION %}
  <div class="pos-row"><span class="k">MARKET</span><span class="v">{{ POSITION.market_slug }}</span></div>
  <div class="pos-row"><span class="k">SIDE</span><span class="v">{{ POSITION.side }}</span></div>
  <div class="pos-row"><span class="k">ENTRY</span><span class="v">{{ '%.4f'|format(POSITION.entry_px or 0) }}</span></div>
  <div class="pos-row"><span class="k">MARK</span><span class="v mark-cell">{% if POSITION.mark is not none %}{{ '%.4f'|format(POSITION.mark) }}{% else %}—{% endif %}</span></div>
  <div class="pos-row"><span class="k">QTY</span><span class="v">{{ '%.4f'|format(POSITION.qty or 0) }}</span></div>
  <div class="pos-row pnl-row">
    <span class="k">P&amp;L</span>
    <span class="v pnl-cell {% if (POSITION.pnl_usd or 0) >= 0 %}pnl-up{% else %}pnl-down{% endif %}">
      {% if POSITION.pnl_usd is not none %}
        {% if POSITION.pnl_usd >= 0 %}+${{ '%.2f'|format(POSITION.pnl_usd) }}{% else %}-${{ '%.2f'|format(-POSITION.pnl_usd) }}{% endif %}
      {% else %}—{% endif %}
    </span>
  </div>
  {% if SHADOW_REC %}
  <div style="margin-top:12px; font-family: var(--font-pixel-text); font-size:18px; color: var(--scoreboard-amber);">
    SHADOW REC: {{ SHADOW_REC }}
  </div>
  {% endif %}
  {% else %}
  <p style="font-family: var(--font-pixel-text); font-size: 20px; color: var(--chalk-dim);">No open position on this game.</p>
  {% endif %}
</div>
```

- [ ] **Step 2: Add game-scoped closed trades + shadow rec lookup**

Append to `dugout_dash/blueprints/game.py` — update both route functions to pass `TRADE_HISTORY` and `SHADOW_REC`. Add helper at bottom:
```python
import sqlite3
from pathlib import Path


def _game_trade_history(game):
    """Closed trades whose slug matches either team abbrev."""
    if not game:
        return []
    away = (game.get("away_abbr") or "").lower()
    home = (game.get("home_abbr") or "").lower()
    with sqlite3.connect(cfg.DB_PATH, timeout=2.0) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT ts_close, market_slug, side, entry_px, exit_px, pnl_usd, reason_close"
            " FROM trades WHERE status='closed'"
            " AND ts_close >= datetime('now','-1 day')"
            " ORDER BY ts_close DESC"
        ).fetchall()
    out = []
    for r in rows:
        slug = (r["market_slug"] or "").lower()
        if away and away in slug or home and home in slug:
            out.append(dict(r))
    return out[:20]


def _shadow_rec(position):
    """Tail the mlb_model shadow log for the latest rec matching this position's slug."""
    if not position:
        return None
    p = Path(cfg.SHADOW_LOG_PATH)
    if not p.exists():
        return None
    try:
        with p.open("r", encoding="utf-8") as f:
            # Tail last ~4KB
            f.seek(0, 2); size = f.tell(); f.seek(max(0, size - 4096))
            lines = f.read().splitlines()
    except Exception:
        return None
    import json as _json
    for line in reversed(lines):
        try:
            rec = _json.loads(line)
        except Exception:
            continue
        if rec.get("market_slug") == position["market_slug"]:
            side = rec.get("recommended_side") or rec.get("side")
            prob = rec.get("model_prob") or rec.get("p")
            if side and prob is not None:
                return f"{side} {float(prob):.2f}"
    return None
```

Then update both `index()` and `detail()` to pass these:
```python
    return render_template(
        "game.html",
        ACTIVE="game",
        GAMES=games,
        SELECTED=selected["espn_id"] if selected else None,
        SELECTED_GAME=selected,
        POSITION=pos,
        TAZZ_URL=_tazz_url(selected),
        TAZZ_FORCE_LINK=cfg.TAZZ_FORCE_LINK,
        SHADOW_REC=_shadow_rec(pos),
        TRADE_HISTORY=_game_trade_history(selected),
        LIVE_COUNT=len(games),
        OPEN_COUNT=len(open_ps),
    )
```
(Store `pos = _match_position(selected, open_ps)` and reuse — both handlers.)

- [ ] **Step 3: Replace trade-history stub in game.html**

In `game.html`, replace the "(filled in Task 21)" panel with:
```html
<div class="panel">
  <h3>── TRADE HISTORY (THIS GAME) ──</h3>
  {% if TRADE_HISTORY %}
  <table>
    <thead><tr><th>CLOSED</th><th>SIDE</th><th>ENTRY</th><th>EXIT</th><th>NET</th><th>REASON</th></tr></thead>
    <tbody>
      {% for t in TRADE_HISTORY %}
      <tr>
        <td>{{ t.ts_close[-8:] if t.ts_close else '' }}</td>
        <td>{{ t.side }}</td>
        <td>{{ '%.4f'|format(t.entry_px or 0) }}</td>
        <td>{{ '%.4f'|format(t.exit_px or 0) }}</td>
        <td class="{% if (t.pnl_usd or 0) >= 0 %}pnl-up{% else %}pnl-down{% endif %}">
          {% if (t.pnl_usd or 0) >= 0 %}+${{ '%.2f'|format(t.pnl_usd or 0) }}{% else %}-${{ '%.2f'|format(-(t.pnl_usd or 0)) }}{% endif %}
        </td>
        <td>{{ t.reason_close or '' }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p style="font-family: var(--font-pixel-text); font-size: 20px; color: var(--chalk-dim);">No closed trades on this game in the last 24 h.</p>
  {% endif %}
</div>
```

- [ ] **Step 4: Smoke test**

```bash
DUGOUT_DASH_PORT=8901 python -m dugout_dash.run &
sleep 25
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8901/
pkill -f dugout_dash.run 2>/dev/null || true
```

Expected: `200`.

- [ ] **Step 5: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add dugout_dash/templates/partials/pos_card.html dugout_dash/templates/game.html dugout_dash/blueprints/game.py && git commit -m "feat(dugout_dash): GAME position card + shadow rec + trade history"
```

---

### Task 22: Tazz URL template test

**Files:**
- Create: `sports_bot_v2/tests/dugout_dash/test_tazz_url.py`

- [ ] **Step 1: Write the test**

Create `sports_bot_v2/tests/dugout_dash/test_tazz_url.py`:
```python
"""Tazz URL derivation from ESPN game dict."""
import pytest

from dugout_dash.blueprints.game import _tazz_url


def test_tazz_url_from_team_abbrevs(monkeypatch):
    from dugout_dash import config as cfg
    monkeypatch.setattr(cfg, "TAZZ_BASE_URL", "https://tazz.tv/mlb/{slug}")
    game = {"away_abbr": "NYY", "home_abbr": "BOS"}
    assert _tazz_url(game) == "https://tazz.tv/mlb/nyy-vs-bos"


def test_tazz_url_none_when_missing_abbrev():
    assert _tazz_url(None) is None
    assert _tazz_url({"away_abbr": "", "home_abbr": "BOS"}) is None
    assert _tazz_url({"away_abbr": "NYY", "home_abbr": ""}) is None
```

- [ ] **Step 2: Run**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && python -m pytest tests/dugout_dash/test_tazz_url.py -v
```

Expected: 2 pass.

- [ ] **Step 3: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add tests/dugout_dash/test_tazz_url.py && git commit -m "test(dugout_dash): tazz URL derivation"
```

---

### Task 23: Orderbook panel in GAME

**Files:**
- Modify: `sports_bot_v2/dugout_dash/blueprints/game.py`
- Modify: `sports_bot_v2/dugout_dash/templates/game.html`

- [ ] **Step 1: Add orderbook fetch helper**

Append to `dugout_dash/blueprints/game.py`:
```python
def _orderbook(position):
    """Best 5 bid/ask for the held side from state_hub."""
    if not position:
        return None
    try:
        from core.state_hub import GLOBAL_STATE_HUB
        snap = GLOBAL_STATE_HUB.snapshot()
    except Exception:
        return None
    row = snap.get(position["market_slug"])
    if not row:
        return None
    return {
        "best_bid": row.get("best_bid"),
        "best_ask": row.get("best_ask"),
        "mark": row.get("current_price"),
        "spread": row.get("spread"),
    }
```

Update both route functions to pass `ORDERBOOK=_orderbook(pos)`.

- [ ] **Step 2: Add orderbook panel to game.html**

In `game.html`, above the trade-history panel (or below the main-grid), add:
```html
{% if ORDERBOOK %}
<div class="panel" style="margin-top:16px;">
  <h3>── ORDERBOOK (HELD SIDE) ──</h3>
  <table>
    <thead><tr><th>BEST BID</th><th>BEST ASK</th><th>MARK</th><th>SPREAD</th></tr></thead>
    <tbody>
      <tr>
        <td>{% if ORDERBOOK.best_bid is not none %}{{ '%.4f'|format(ORDERBOOK.best_bid) }}{% else %}—{% endif %}</td>
        <td>{% if ORDERBOOK.best_ask is not none %}{{ '%.4f'|format(ORDERBOOK.best_ask) }}{% else %}—{% endif %}</td>
        <td class="mark-cell">{% if ORDERBOOK.mark is not none %}{{ '%.4f'|format(ORDERBOOK.mark) }}{% else %}—{% endif %}</td>
        <td>{% if ORDERBOOK.spread is not none %}{{ '%.4f'|format(ORDERBOOK.spread) }}{% else %}—{% endif %}</td>
      </tr>
    </tbody>
  </table>
</div>
{% endif %}
```

- [ ] **Step 3: Smoke test + commit**

```bash
DUGOUT_DASH_PORT=8901 python -m dugout_dash.run &
sleep 3
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8901/
pkill -f dugout_dash.run 2>/dev/null || true
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add dugout_dash/blueprints/game.py dugout_dash/templates/game.html && git commit -m "feat(dugout_dash): orderbook panel on GAME (best bid/ask/mark/spread)"
```

---

## Phase 4 — SYSTEM + HALL OF FAME (Tasks 24–28)

### Task 24: SYSTEM page — heartbeat, gates, controls

**Files:**
- Create: `sports_bot_v2/dugout_dash/blueprints/system.py`
- Create: `sports_bot_v2/dugout_dash/templates/system.html`
- Modify: `sports_bot_v2/dugout_dash/__init__.py`

- [ ] **Step 1: Write system blueprint**

Create `sports_bot_v2/dugout_dash/blueprints/system.py`:
```python
"""SYSTEM page — bot heartbeat, guardrails, controls."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

from flask import Blueprint, render_template, jsonify, request

from dugout_dash import config as cfg
from dugout_dash.events import GLOBAL_EVENT_BUS

bp = Blueprint("system", __name__)


def _read_state():
    p = Path(cfg.STATE_PATH)
    if not p.exists():
        return {"exists": False}
    try:
        return {"exists": True, "mtime": p.stat().st_mtime, "data": json.loads(p.read_text(encoding="utf-8"))}
    except Exception as e:
        return {"exists": True, "error": str(e)}


def _today_pnl():
    try:
        with sqlite3.connect(cfg.DB_PATH, timeout=2.0) as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(pnl_usd),0), COUNT(*), "
                " SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END)"
                " FROM trades WHERE status='closed'"
                " AND ts_close >= datetime('now','-1 day')"
            ).fetchone()
            pnl, total, wins = (row[0] or 0.0), (row[1] or 0), (row[2] or 0)
            win_rate = (wins / total * 100.0) if total else None
            return {"pnl": pnl, "trades": total, "win_rate_pct": win_rate}
    except Exception as e:
        return {"error": str(e)}


@bp.route("/system")
def index():
    st = _read_state()
    stale = True
    if st.get("exists") and "mtime" in st:
        stale = (time.time() - st["mtime"]) > 90.0
    return render_template(
        "system.html",
        ACTIVE="system",
        STATE=st,
        STALE=stale,
        TODAY=_today_pnl(),
        SSE_CLIENT_COUNT=GLOBAL_EVENT_BUS.subscriber_count(),
    )


@bp.route("/api/control/<action>", methods=["POST"])
def control(action: str):
    if action not in {"pause", "resume", "flat_all"}:
        return {"error": "unknown action"}, 400
    path = Path(cfg.STATE_PATH)
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        data = {}
    if action == "pause":
        data["bot_paused"] = True
    elif action == "resume":
        data["bot_paused"] = False
    elif action == "flat_all":
        data["flat_all_request_ts"] = time.time()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return {"ok": True, "action": action}
    except Exception as e:
        return {"error": str(e)}, 500
```

- [ ] **Step 2: Write system.html**

Create `sports_bot_v2/dugout_dash/templates/system.html`:
```html
{% extends "base.html" %}
{% block title %}SYSTEM · Dugout Dash{% endblock %}
{% block content %}
<section class="pane">

  <div class="panel" style="margin-bottom:16px;">
    <h3>── HEARTBEAT ──</h3>
    <div class="pos-row"><span class="k">STATE</span><span class="v">
      {% if STALE %}<span class="pnl-down">⚠ STALE</span>
      {% elif STATE.exists %}<span class="pnl-up">● ALIVE</span>
      {% else %}<span class="pnl-down">? NO STATE</span>{% endif %}
    </span></div>
    {% if STATE.mtime %}
    <div class="pos-row"><span class="k">LAST TICK</span><span class="v">{{ (STATE.mtime * 1000)|int }}</span></div>
    {% endif %}
    {% if STATE.data and STATE.data.bot_paused %}
    <div class="pos-row"><span class="k">MODE</span><span class="v pnl-down">PAUSED</span></div>
    {% endif %}
  </div>

  <div class="panel" style="margin-bottom:16px;">
    <h3>── TODAY ──</h3>
    <div class="pos-row"><span class="k">P&amp;L</span>
      <span class="v {% if (TODAY.pnl or 0) >= 0 %}pnl-up{% else %}pnl-down{% endif %}">
        {% if (TODAY.pnl or 0) >= 0 %}+${{ '%.2f'|format(TODAY.pnl or 0) }}{% else %}-${{ '%.2f'|format(-(TODAY.pnl or 0)) }}{% endif %}
      </span></div>
    <div class="pos-row"><span class="k">TRADES</span><span class="v">{{ TODAY.trades or 0 }}</span></div>
    <div class="pos-row"><span class="k">WIN RATE</span><span class="v">{% if TODAY.win_rate_pct is not none %}{{ '%.1f'|format(TODAY.win_rate_pct) }}%{% else %}—{% endif %}</span></div>
  </div>

  <div class="panel" style="margin-bottom:16px;">
    <h3>── STREAMS ──</h3>
    <div class="pos-row"><span class="k">SSE CLIENTS</span><span class="v">{{ SSE_CLIENT_COUNT }}</span></div>
  </div>

  <div class="panel" style="margin-bottom:16px;">
    <h3>── GUARD GATES (9) ──</h3>
    <div class="gates" id="guard-gates">
      {% for i in range(9) %}<span class="gate" data-gate-idx="{{ i }}" title="gate {{ i }} — awaiting data"></span>{% endfor %}
    </div>
    <div style="font-family: var(--font-pixel-text); font-size: 16px; color: var(--chalk-dim); margin-top: 8px;">
      Lights up on incoming <code>guard_state</code> SSE events. Bot instrumentation point is a follow-up: have <code>bot_core.py</code> publish <code>guard_state</code> with a 9-bool array after each risk evaluation.
    </div>
  </div>

  <div class="panel">
    <h3>── CONTROLS ──</h3>
    <div style="display:flex; gap:12px; flex-wrap:wrap;">
      <button class="tazz-watch-btn" onclick="ctl('pause')">⏸ PAUSE BOT</button>
      <button class="tazz-watch-btn" onclick="ctl('resume')">▶ RESUME BOT</button>
      <button class="tazz-watch-btn" style="border-color: var(--foul-red);" onclick="ctl('flat_all')">🚨 FLAT ALL</button>
    </div>
  </div>

</section>
{% block scripts %}
<script>
async function ctl(action) {
  if (action === 'flat_all' && !confirm('FLAT ALL — close every open position. Confirm?')) return;
  const r = await fetch('/api/control/' + action, { method: 'POST' });
  const j = await r.json();
  if (j.ok) setTimeout(() => location.reload(), 400);
  else alert('Control failed: ' + (j.error || r.status));
}

// Listen for guard_state events from SSE — payload: {gates: [bool×9], bot_mode, ts}
window.addEventListener('DOMContentLoaded', () => {
  if (typeof EventSource === 'undefined') return;
  const es = new EventSource('/api/events');
  es.addEventListener('guard_state', (e) => {
    try {
      const p = JSON.parse(e.data);
      const gates = p.gates || [];
      document.querySelectorAll('#guard-gates .gate').forEach((el, i) => {
        el.classList.remove('on', 'off');
        if (gates[i] === true) el.classList.add('on');
        else if (gates[i] === false) el.classList.add('off');
      });
    } catch (err) {}
  });
});
</script>
{% endblock %}
{% endblock %}
```

- [ ] **Step 3: Register blueprint**

Edit `dugout_dash/__init__.py`:
```python
from dugout_dash.blueprints import system as system_bp
# ...
app.register_blueprint(system_bp.bp)
```

- [ ] **Step 4: Smoke test**

```bash
DUGOUT_DASH_PORT=8901 python -m dugout_dash.run &
sleep 2
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8901/system
pkill -f dugout_dash.run 2>/dev/null || true
```

Expected: `200`.

- [ ] **Step 5: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add dugout_dash/blueprints/system.py dugout_dash/templates/system.html dugout_dash/__init__.py && git commit -m "feat(dugout_dash): SYSTEM page with heartbeat, today P&L, controls"
```

---

### Task 25: Hall-of-Fame SQL module

**Files:**
- Create: `sports_bot_v2/dugout_dash/hof_sql.py`
- Create: `sports_bot_v2/tests/dugout_dash/test_hof_sql.py`

- [ ] **Step 1: Write the failing test**

Create `sports_bot_v2/tests/dugout_dash/test_hof_sql.py`:
```python
"""hof_sql — seeded in-memory DB, each query returns expected shape."""
import sqlite3
import tempfile
from pathlib import Path

import pytest


def _seed_db(path):
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE trades (
            id INTEGER PRIMARY KEY, ts_open TEXT, ts_close TEXT,
            market_slug TEXT, market_id TEXT, side TEXT, qty REAL,
            entry_px REAL, exit_px REAL, pnl_usd REAL, fees_usd REAL,
            reason_open TEXT, reason_close TEXT, confidence REAL,
            mode TEXT, status TEXT, sport TEXT
        )""")
    rows = [
        # (slug, side, entry, exit, pnl, reason_close, ts_open, ts_close)
        ("yankees-win", "BUY_YES", 0.50, 0.60, 10.00, "TAKE_PROFIT", "2026-04-16 18:00:00", "2026-04-16 20:00:00"),
        ("yankees-win", "BUY_YES", 0.55, 0.40, -15.00, "STOP_LOSS",   "2026-04-17 18:00:00", "2026-04-17 19:30:00"),
        ("red-sox-win", "BUY_YES", 0.48, 0.70, 22.00, "TAKE_PROFIT", "2026-04-17 19:00:00", "2026-04-17 22:00:00"),
        ("red-sox-win", "BUY_YES", 0.50, 0.55,  5.00, "TAKE_PROFIT", "2026-04-18 18:00:00", "2026-04-18 19:00:00"),
    ]
    for i, r in enumerate(rows, 1):
        conn.execute(
            "INSERT INTO trades (id, market_slug, side, entry_px, exit_px, pnl_usd, reason_close, ts_open, ts_close, status)"
            " VALUES (?,?,?,?,?,?,?,?,?,'closed')",
            (i, *r),
        )
    conn.commit()
    conn.close()


def _team_from_slug(slug: str) -> str:
    # Trivial heuristic for the test DB: first word before '-win'
    return slug.split("-win")[0]


def test_batting_avg(tmp_path):
    db = tmp_path / "t.db"
    _seed_db(db)
    import dugout_dash.hof_sql as hof
    hof.reset_cache()
    assert hof.batting_avg(db_path=str(db)) == pytest.approx(3/4)


def test_slugging_era(tmp_path):
    db = tmp_path / "t.db"
    _seed_db(db)
    import dugout_dash.hof_sql as hof
    hof.reset_cache()
    assert hof.slugging(db_path=str(db)) == pytest.approx((10+22+5)/3)
    assert hof.era(db_path=str(db)) == pytest.approx(-15.0)


def test_mvp_day(tmp_path):
    db = tmp_path / "t.db"
    _seed_db(db)
    import dugout_dash.hof_sql as hof
    hof.reset_cache()
    mvp = hof.mvp_day(db_path=str(db))
    # 2026-04-17 is  -15 + 22 = 7; 2026-04-16 is 10; 2026-04-18 is 5.
    # Best single day = 2026-04-16 with 10.
    assert mvp is not None
    assert mvp["day"] == "2026-04-16"
    assert mvp["pnl"] == pytest.approx(10.0)


def test_team_records_requires_team_resolver(tmp_path):
    db = tmp_path / "t.db"
    _seed_db(db)
    import dugout_dash.hof_sql as hof
    hof.reset_cache()
    records = hof.team_records(db_path=str(db), team_from_slug=_team_from_slug)
    by_team = {r["team"]: r for r in records}
    assert by_team["yankees"]["wins"] == 1 and by_team["yankees"]["losses"] == 1
    assert by_team["red-sox"]["wins"] == 2 and by_team["red-sox"]["losses"] == 0
    assert by_team["red-sox"]["pnl"] == pytest.approx(27.0)
```

- [ ] **Step 2: Run — fails**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && python -m pytest tests/dugout_dash/test_hof_sql.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement hof_sql**

Create `sports_bot_v2/dugout_dash/hof_sql.py`:
```python
"""Hall-of-Fame SQL queries. 60s in-memory cache keyed by (fn, db_path)."""
from __future__ import annotations

import sqlite3
import threading
import time
from typing import Any, Callable

from dugout_dash import config as cfg

_cache: dict[tuple, tuple[float, Any]] = {}
_lock = threading.Lock()


def reset_cache() -> None:
    with _lock:
        _cache.clear()


def _cached(fn_name: str, db_path: str, compute: Callable[[], Any]) -> Any:
    key = (fn_name, db_path)
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and (now - hit[0] < cfg.HOF_CACHE_TTL_SEC):
            return hit[1]
    val = compute()
    with _lock:
        _cache[key] = (now, val)
    return val


def _conn(db_path: str) -> sqlite3.Connection:
    c = sqlite3.connect(db_path, timeout=2.0)
    c.row_factory = sqlite3.Row
    return c


def batting_avg(db_path: str | None = None) -> float | None:
    db_path = db_path or cfg.DB_PATH
    def _compute():
        with _conn(db_path) as c:
            row = c.execute(
                "SELECT SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END), COUNT(*) "
                "FROM trades WHERE status='closed'"
            ).fetchone()
            wins, total = (row[0] or 0), (row[1] or 0)
            return (wins / total) if total else None
    return _cached("batting_avg", db_path, _compute)


def slugging(db_path: str | None = None) -> float | None:
    db_path = db_path or cfg.DB_PATH
    def _compute():
        with _conn(db_path) as c:
            row = c.execute(
                "SELECT AVG(pnl_usd) FROM trades WHERE status='closed' AND pnl_usd > 0"
            ).fetchone()
            return row[0]
    return _cached("slugging", db_path, _compute)


def era(db_path: str | None = None) -> float | None:
    db_path = db_path or cfg.DB_PATH
    def _compute():
        with _conn(db_path) as c:
            row = c.execute(
                "SELECT AVG(pnl_usd) FROM trades WHERE status='closed' AND pnl_usd < 0"
            ).fetchone()
            return row[0]
    return _cached("era", db_path, _compute)


def mvp_day(db_path: str | None = None) -> dict | None:
    db_path = db_path or cfg.DB_PATH
    def _compute():
        with _conn(db_path) as c:
            row = c.execute(
                "SELECT DATE(ts_close) d, SUM(pnl_usd) p FROM trades"
                " WHERE status='closed' GROUP BY d ORDER BY p DESC LIMIT 1"
            ).fetchone()
            if not row or row["p"] is None:
                return None
            return {"day": row["d"], "pnl": row["p"]}
    return _cached("mvp_day", db_path, _compute)


def no_hitter(db_path: str | None = None) -> dict | None:
    db_path = db_path or cfg.DB_PATH
    def _compute():
        with _conn(db_path) as c:
            rows = c.execute(
                "SELECT DATE(ts_close) d, SUM(CASE WHEN pnl_usd>0 THEN 1 ELSE 0 END) w, COUNT(*) n "
                "FROM trades WHERE status='closed' GROUP BY d"
            ).fetchall()
        days = [r for r in rows if r["n"] > 0 and r["w"] == r["n"]]
        if not days:
            return None
        return {"count": len(days), "most_recent": max(r["d"] for r in days)}
    return _cached("no_hitter", db_path, _compute)


def team_records(
    db_path: str | None = None,
    team_from_slug: Callable[[str], str] | None = None,
) -> list[dict]:
    """Requires a team-from-slug resolver (production uses mlb adapter)."""
    db_path = db_path or cfg.DB_PATH
    if team_from_slug is None:
        try:
            from sports.mlb.adapter import team_from_slug as _resolver
            team_from_slug = _resolver
        except Exception:
            team_from_slug = lambda s: s.split("-")[0]
    def _compute():
        with _conn(db_path) as c:
            rows = c.execute(
                "SELECT market_slug, pnl_usd FROM trades WHERE status='closed'"
            ).fetchall()
        agg: dict[str, dict] = {}
        for r in rows:
            team = team_from_slug(r["market_slug"] or "")
            a = agg.setdefault(team, {"team": team, "wins": 0, "losses": 0, "pnl": 0.0, "trades": 0})
            pnl = r["pnl_usd"] or 0.0
            a["pnl"] += pnl
            a["trades"] += 1
            if pnl > 0: a["wins"] += 1
            elif pnl < 0: a["losses"] += 1
        out = list(agg.values())
        for a in out:
            a["batting_avg"] = (a["wins"] / a["trades"]) if a["trades"] else None
        out.sort(key=lambda x: x["pnl"], reverse=True)
        return out
    return _cached("team_records", db_path, _compute)


def dynasty(db_path: str | None = None, team_from_slug=None) -> dict | None:
    recs = team_records(db_path=db_path, team_from_slug=team_from_slug)
    return recs[0] if recs else None


def rookie_of_the_year(db_path: str | None = None, team_from_slug=None) -> dict | None:
    """Newest team (by first-traded date) with positive cumulative P&L."""
    db_path = db_path or cfg.DB_PATH
    if team_from_slug is None:
        try:
            from sports.mlb.adapter import team_from_slug as _resolver
            team_from_slug = _resolver
        except Exception:
            team_from_slug = lambda s: s.split("-")[0]
    def _compute():
        with _conn(db_path) as c:
            rows = c.execute(
                "SELECT market_slug, ts_open, pnl_usd FROM trades WHERE status='closed'"
            ).fetchall()
        firsts: dict[str, str] = {}
        pnls: dict[str, float] = {}
        for r in rows:
            team = team_from_slug(r["market_slug"] or "")
            ts = r["ts_open"]
            if team not in firsts or ts < firsts[team]:
                firsts[team] = ts
            pnls[team] = pnls.get(team, 0.0) + (r["pnl_usd"] or 0.0)
        profitable = [(t, firsts[t], pnls[t]) for t in firsts if pnls[t] > 0]
        if not profitable:
            return None
        profitable.sort(key=lambda x: x[1], reverse=True)  # newest first
        t, first, pnl = profitable[0]
        return {"team": t, "first_trade": first, "pnl": pnl}
    return _cached("rookie_of_the_year", db_path, _compute)
```

- [ ] **Step 4: Run — passes**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && python -m pytest tests/dugout_dash/test_hof_sql.py -v
```

Expected: 4 pass.

- [ ] **Step 5: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add dugout_dash/hof_sql.py tests/dugout_dash/test_hof_sql.py && git commit -m "feat(dugout_dash): hof_sql queries + 60s cache + tests"
```

---

### Task 26: Hall of Fame page

**Files:**
- Create: `sports_bot_v2/dugout_dash/blueprints/hof.py`
- Create: `sports_bot_v2/dugout_dash/templates/hof.html`
- Modify: `sports_bot_v2/dugout_dash/__init__.py`

- [ ] **Step 1: Write hof blueprint**

Create `sports_bot_v2/dugout_dash/blueprints/hof.py`:
```python
"""Hall of Fame page."""
from __future__ import annotations
from flask import Blueprint, render_template, redirect, url_for

from dugout_dash import hof_sql

bp = Blueprint("hof", __name__)


@bp.route("/hof")
def index():
    return render_template(
        "hof.html",
        ACTIVE="hof",
        BATTING_AVG=hof_sql.batting_avg(),
        SLUGGING=hof_sql.slugging(),
        ERA=hof_sql.era(),
        MVP_DAY=hof_sql.mvp_day(),
        NO_HITTER=hof_sql.no_hitter(),
        TEAM_RECORDS=hof_sql.team_records(),
        DYNASTY=hof_sql.dynasty(),
        ROOKIE=hof_sql.rookie_of_the_year(),
    )


@bp.route("/hof/refresh")
def refresh():
    hof_sql.reset_cache()
    return redirect(url_for("hof.index"))
```

- [ ] **Step 2: Write hof.html**

Create `sports_bot_v2/dugout_dash/templates/hof.html`:
```html
{% extends "base.html" %}
{% block title %}HALL OF FAME · Dugout Dash{% endblock %}
{% block content %}
<section class="pane">
  <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:12px;">
    <h2 style="font-family: var(--font-pixel); color: var(--scoreboard-amber);">HALL OF FAME</h2>
    <a class="tazz-watch-btn" href="{{ url_for('hof.refresh') }}">⟳ REFRESH</a>
  </div>

  <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap:16px;">

    <div class="pos-card" style="border-color: var(--hr-gold);">
      <h3>── BATTING AVG ──</h3>
      <div style="font-family: var(--font-pixel); font-size: 32px; color: var(--hr-gold); text-align:center; padding: 12px 0;">
        {% if BATTING_AVG is not none %}.{{ '%03d'|format((BATTING_AVG * 1000)|int) }}{% else %}.---{% endif %}
      </div>
    </div>

    <div class="pos-card">
      <h3>── SLUGGING ──</h3>
      <div class="pos-row"><span class="k">AVG WIN</span><span class="v pnl-up">{% if SLUGGING is not none %}+${{ '%.2f'|format(SLUGGING) }}{% else %}—{% endif %}</span></div>
    </div>

    <div class="pos-card" style="border-color: var(--foul-red);">
      <h3>── ERA ──</h3>
      <div class="pos-row"><span class="k">AVG LOSS</span><span class="v pnl-down">{% if ERA is not none %}-${{ '%.2f'|format(-ERA) }}{% else %}—{% endif %}</span></div>
    </div>

    <div class="pos-card">
      <h3>── MVP DAY ──</h3>
      {% if MVP_DAY %}
      <div class="pos-row"><span class="k">DATE</span><span class="v">{{ MVP_DAY.day }}</span></div>
      <div class="pos-row"><span class="k">P&amp;L</span><span class="v pnl-up">+${{ '%.2f'|format(MVP_DAY.pnl) }}</span></div>
      {% else %}<p style="font-family: var(--font-pixel-text); font-size: 20px; color: var(--chalk-dim);">None yet.</p>{% endif %}
    </div>

    <div class="pos-card">
      <h3>── NO-HITTER ──</h3>
      {% if NO_HITTER %}
      <div class="pos-row"><span class="k">COUNT</span><span class="v">{{ NO_HITTER.count }}</span></div>
      <div class="pos-row"><span class="k">LATEST</span><span class="v">{{ NO_HITTER.most_recent }}</span></div>
      {% else %}<p style="font-family: var(--font-pixel-text); font-size: 20px; color: var(--chalk-dim);">None yet.</p>{% endif %}
    </div>

    <div class="pos-card" style="border-color: var(--hr-gold);">
      <h3>── DYNASTY 🏆 ──</h3>
      {% if DYNASTY %}
      <div class="pos-row"><span class="k">TEAM</span><span class="v">{{ DYNASTY.team }}</span></div>
      <div class="pos-row"><span class="k">P&amp;L</span><span class="v {% if DYNASTY.pnl >= 0 %}pnl-up{% else %}pnl-down{% endif %}">{% if DYNASTY.pnl >= 0 %}+${{ '%.2f'|format(DYNASTY.pnl) }}{% else %}-${{ '%.2f'|format(-DYNASTY.pnl) }}{% endif %}</span></div>
      {% else %}<p style="font-family: var(--font-pixel-text); font-size: 20px; color: var(--chalk-dim);">No closed trades yet.</p>{% endif %}
    </div>

    <div class="pos-card">
      <h3>── ROOKIE OF THE YEAR ──</h3>
      {% if ROOKIE %}
      <div class="pos-row"><span class="k">TEAM</span><span class="v">{{ ROOKIE.team }}</span></div>
      <div class="pos-row"><span class="k">P&amp;L</span><span class="v pnl-up">+${{ '%.2f'|format(ROOKIE.pnl) }}</span></div>
      {% else %}<p style="font-family: var(--font-pixel-text); font-size: 20px; color: var(--chalk-dim);">None yet.</p>{% endif %}
    </div>

  </div>

  <div class="panel" style="margin-top:16px;">
    <h3>── TEAM RECORDS ──</h3>
    {% if TEAM_RECORDS %}
    <table>
      <thead><tr><th>TEAM</th><th>W</th><th>L</th><th>BA</th><th>P&amp;L</th></tr></thead>
      <tbody>
        {% for r in TEAM_RECORDS %}
        <tr>
          <td>{{ r.team }}</td>
          <td>{{ r.wins }}</td>
          <td>{{ r.losses }}</td>
          <td>{% if r.batting_avg is not none %}.{{ '%03d'|format((r.batting_avg * 1000)|int) }}{% else %}.---{% endif %}</td>
          <td class="{% if r.pnl >= 0 %}pnl-up{% else %}pnl-down{% endif %}">{% if r.pnl >= 0 %}+${{ '%.2f'|format(r.pnl) }}{% else %}-${{ '%.2f'|format(-r.pnl) }}{% endif %}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}<p style="font-family: var(--font-pixel-text); font-size: 20px; color: var(--chalk-dim);">No closed trades yet.</p>{% endif %}
  </div>

</section>
{% endblock %}
```

- [ ] **Step 3: Register blueprint**

Edit `dugout_dash/__init__.py`:
```python
from dugout_dash.blueprints import hof as hof_bp
# ...
app.register_blueprint(hof_bp.bp)
```

- [ ] **Step 4: Smoke test**

```bash
DUGOUT_DASH_PORT=8901 python -m dugout_dash.run &
sleep 2
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8901/hof
pkill -f dugout_dash.run 2>/dev/null || true
```

Expected: `200`.

- [ ] **Step 5: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add dugout_dash/blueprints/hof.py dugout_dash/templates/hof.html dugout_dash/__init__.py && git commit -m "feat(dugout_dash): HALL OF FAME page with baseball-card grid"
```

---

### Task 27: Update context processor — live counts from state/DB

**Files:**
- Modify: `sports_bot_v2/dugout_dash/__init__.py`

- [ ] **Step 1: Replace the static inject_globals with live values**

Edit the `inject_globals` context processor in `dugout_dash/__init__.py`:
```python
    @app.context_processor
    def inject_globals():
        open_count = 0
        today_pnl = 0.0
        bankroll = cfg.STARTING_BANKROLL
        try:
            import sqlite3
            with sqlite3.connect(cfg.DB_PATH, timeout=1.5) as conn:
                open_count = conn.execute(
                    "SELECT COUNT(*) FROM trades WHERE status='open'"
                ).fetchone()[0] or 0
                today_pnl = conn.execute(
                    "SELECT COALESCE(SUM(pnl_usd),0) FROM trades"
                    " WHERE status='closed' AND ts_close >= datetime('now','-1 day')"
                ).fetchone()[0] or 0.0
                realized = conn.execute(
                    "SELECT COALESCE(SUM(pnl_usd),0) FROM trades WHERE status='closed'"
                ).fetchone()[0] or 0.0
                bankroll = cfg.STARTING_BANKROLL + realized
        except Exception:
            pass
        live_count = 0
        try:
            from core import espn_cache
            games = espn_cache.get_scoreboard().get("games", [])
            live_count = sum(1 for g in games if g.get("inning", 0) > 0 and g.get("status") != "STATUS_FINAL")
        except Exception:
            pass
        return {
            "PORT": cfg.PORT,
            "DB_PATH": cfg.DB_PATH,
            "BOT_VERSION": "0.4.2",
            "BANKROLL": float(bankroll),
            "TODAY_PNL": float(today_pnl),
            "LIVE_COUNT": live_count,
            "OPEN_COUNT": open_count,
        }
```

- [ ] **Step 2: Smoke test**

```bash
DUGOUT_DASH_PORT=8901 python -m dugout_dash.run &
sleep 3
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8901/
pkill -f dugout_dash.run 2>/dev/null || true
```

Expected: `200`. Every page's scoreboard chip shows live bankroll and today P&L.

- [ ] **Step 3: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add dugout_dash/__init__.py && git commit -m "feat(dugout_dash): global chips show live bankroll/today-pnl/counts"
```

---

### Task 28: End-to-end manual test — synthetic bot run

**Files:**
- (no code changes — verification only)

- [ ] **Step 1: Start dugout_dash on 8900 (real port this time)**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && DUGOUT_DASH_PORT=8900 python -m dugout_dash.run &
sleep 3
```

- [ ] **Step 2: Open all five pages**

In browser:
- http://127.0.0.1:8900/
- http://127.0.0.1:8900/trades
- http://127.0.0.1:8900/tape
- http://127.0.0.1:8900/system
- http://127.0.0.1:8900/hof

Click once on each to enable sound + allow notifications.

- [ ] **Step 3: Run a synthetic bot iteration**

If `bot_core.py` has a `--synthetic N` mode (per march_madness_bot sibling), invoke it:
```bash
SPORT=baseball python bot_core.py --synthetic 2 &
```
If the flag doesn't exist, drive the EventBus directly:
```bash
curl -s -X POST http://127.0.0.1:8900/api/events/test_publish -H 'Content-Type: application/json' -d '{"type":"trade_entered","payload":{"trade_id":9001,"slug":"e2e-test-slug","side":"BUY_YES","entry_px":0.48,"qty":208.33,"size_usd":100,"mode":"neutral","confidence":0.72,"ts":"2026-04-18T20:00:00"}}'
for v in 0.49 0.51 0.53 0.56 0.60 0.63; do
  curl -s -X POST http://127.0.0.1:8900/api/events/test_publish -H 'Content-Type: application/json' -d "{\"type\":\"mark_update\",\"payload\":{\"slug\":\"e2e-test-slug\",\"mark\":$v}}"
  sleep 0.5
done
curl -s -X POST http://127.0.0.1:8900/api/events/test_publish -H 'Content-Type: application/json' -d '{"type":"trade_exited","payload":{"trade_id":9001,"slug":"e2e-test-slug","side":"BUY_YES","entry_px":0.48,"exit_px":0.63,"net_pnl":31.25,"reason":"TAKE_PROFIT","ts":"2026-04-18T20:05:00"}}'
```

(Requires `DUGOUT_DASH_DEV=1` in env for `/api/events/test_publish` — start it that way for this verification.)

- [ ] **Step 4: Verify**

- Toast "BASE HIT — TRADE FILLED" appears.
- OS notification pops (if permission).
- `base_hit.wav` plays.
- TRADES page gets a new OPEN row.
- Mark updates: P&L cell flashes and toggles green/red.
- TAPE sparkline evolves.
- On exit: "WALK-OFF — TRADE CLOSED" toast, `walkoff.wav`, row animates out.

If all five happen within one second of the bot's action, the realtime contract is met.

- [ ] **Step 5: Stop**

```bash
pkill -f dugout_dash.run 2>/dev/null || true
pkill -f "bot_core.py" 2>/dev/null || true
```

- [ ] **Step 6: Commit a verification note**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && echo "Phase 4 e2e verification: $(date -u +%FT%TZ) — all pages, all events, all sounds/toasts, all realtime updates verified under 1s." >> docs/superpowers/plans/dugout_dash_verification.log && git add docs/superpowers/plans/dugout_dash_verification.log && git commit -m "docs(dugout_dash): Phase 4 end-to-end verification log"
```

---

## Phase 5 — Cutover (Tasks 29–30)

### Task 29: Retire old dashboard

**Files:**
- Delete: `sports_bot_v2/dashboard_server.py`
- Delete: `sports_bot_v2/dashboard.html`
- Delete: `sports_bot_v2/dashboard_v2.html`
- Modify: `sports_bot_v2/dugout_dash_mockup.html` — delete (no longer needed)

- [ ] **Step 1: Confirm no other code imports dashboard_server**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && grep -rn "dashboard_server" --include="*.py" . | grep -v dugout_dash
```

Expected: no results (or only references in scripts/docs, which are fine).

- [ ] **Step 2: Delete the old files**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && rm dashboard_server.py dashboard.html dashboard_v2.html dugout_dash_mockup.html
```

- [ ] **Step 3: Update run scripts / docs**

Look for any launch scripts or docs that reference `dashboard_server`:
```bash
grep -rln "dashboard_server\|dashboard\.html" --include="*.sh" --include="*.md" --include="*.bat" --include="*.ps1" .
```

For each hit, change the invocation to `python -m dugout_dash.run` (or leave a stub pointing at the new module).

- [ ] **Step 4: Smoke test real port 8900 start-to-finish**

```bash
DUGOUT_DASH_PORT=8900 python -m dugout_dash.run &
sleep 3
for p in / /trades /tape /system /hof; do
  echo -n "$p: "; curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8900$p
done
pkill -f dugout_dash.run 2>/dev/null || true
```

Expected: all `200`.

- [ ] **Step 5: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add -A && git commit -m "chore(dugout_dash): retire legacy dashboard_server.py + html files"
```

---

### Task 30: Update .env.example + README pointer

**Files:**
- Modify: `sports_bot_v2/.env.example` (create if missing)
- Modify: `sports_bot_v2/README.md` (if present)

- [ ] **Step 1: Add new env vars to .env.example**

Append (or create the file with) these entries:
```
# --- dugout_dash (port 8900) ---
DUGOUT_DASH_PORT=8900
DUGOUT_DASH_HOST=0.0.0.0
# {slug} gets replaced with "<away_abbr>-vs-<home_abbr>" in lowercase
TAZZ_BASE_URL=https://tazz.tv/mlb/{slug}
# Skip the iframe attempt and go straight to the deep-link button
TAZZ_FORCE_LINK=0
TAZZ_IFRAME_TIMEOUT_MS=3000
# Upper cap on mark_update events per slug per second
DUGOUT_MARK_UPDATE_HZ=5
# Hall-of-Fame cache TTL (seconds)
DUGOUT_HOF_CACHE_TTL=60
# Set to 1 to enable /api/events/test_publish (dev only)
DUGOUT_DASH_DEV=0
```

- [ ] **Step 2: Add a README pointer**

If `README.md` exists, append a section:
```markdown
## Dugout Dash — live dashboard

Port 8900. 8-bit baseball UI; 5 pages (GAME, TRADES, TAPE, SYSTEM, HALL OF FAME);
realtime trade + price updates via SSE.

```bash
python -m dugout_dash.run
```

Design doc: `docs/superpowers/specs/2026-04-18-dugout-dash-port-8900-design.md`
Plan: `docs/superpowers/plans/2026-04-18-dugout-dash-port-8900.md`
```

- [ ] **Step 3: Commit**

```bash
cd /c/Users/johnny/Desktop/sports_bot_v2 && git add .env.example README.md 2>/dev/null; git commit -m "docs(dugout_dash): .env.example + README pointer"
```

---

## Self-review checklist for the implementer

After all 30 tasks are complete, verify:

1. **All 5 pages load on 8900** — status 200 from `/`, `/trades`, `/tape`, `/system`, `/hof`.
2. **SSE round-trip under 500 ms** — synthetic `trade_entered` published in bot process reaches browser toast in under half a second.
3. **P&L cells flash and settle correctly** — green on gains, red on losses, direction flashes only on tick transitions.
4. **All four tests pass** — `pytest tests/dugout_dash/ -v` reports green for event_bus, market_tap, hof_sql, tazz_url, sse_endpoint.
5. **Tazz fallback triggers** — block tazz.tv in your browser's network panel, reload GAME, verify the watch-on-tazz button appears.
6. **Notifications work** — after clicking once on the page, a trade_entered triggers an OS notification.
7. **Legacy dashboard is gone** — `dashboard_server.py` / `dashboard.html` removed; no references remain.
