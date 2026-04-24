# Control Plane Redesign — "Dugout OS"

**Date:** 2026-04-18
**Author:** operator + claude (brainstormed)
**Status:** design approved, awaiting implementation plan
**Scope:** full visual + interaction redesign of the operator control plane at `127.0.0.1:8787` (`mlbbot\control_plane\`), plus a new roster-management feature (release / sign replacement / graveyard).

---

## 1. Why

The current "Terminal Ledger" UI is dense and functional but feels like a rough draft: tiny buttons, muted chips, no visual hierarchy to separate live work from background state. The operator watches the live betting bot for hours and wants the surface they work in to feel alive and **fun** — not just a dashboard. The redesign is a morale / engagement investment first, with two incidental functional wins:

1. A prominent, impossible-to-miss "draft a new task" CTA, replacing the current 24-pixel "+ New Task" button tucked in the top bar.
2. A roster-management surface that lets the operator release / replace agent personas over time, giving the system narrative continuity and stakes.

## 2. Non-goals

- Changing any backend contract. Every route, endpoint, DB column name, JS function, `data-*` hook, API payload, and workflow-state enum stays identical.
- Renaming workflow states. Lane renames are **display-only** (via `LANE_DISPLAY` in `workflow.py` plus `templates/_lane_labels.py` or equivalent); the underlying enum (`DRAFT`, `READY_FOR_WORKER`, `RUNNING`, `AWAITING_REVIEW`, `CHANGES_REQUESTED`, `BLOCKED`, `DONE`, `LIVE`, `ARCHIVED`) is untouched.
- Changing role/adapter/model selection. Trading a persona is cosmetic only — it swaps display name / icon / color / jersey number / tagline, never the underlying `role`, `adapter`, or `model` fields used by dispatch.
- Mobile or responsive below ~1200px. The control plane is an operator-only desktop surface at `127.0.0.1:8787`; we target 1440-1920px with graceful degradation, nothing more.

## 3. Design language — "8-bit arcade baseball"

**Theme:** NES-era arcade baseball game (RBI Baseball, Baseball Stars) reinterpreted with modern crispness. Stadium-night palette, pixel display type for scoreboard elements, smooth sans for body copy, pixel-art player sprites.

**Palette (CSS custom properties to add to `static/app.css`):**

```
--field-night:    #0a1628   /* base bg — stadium night sky */
--field-deep:     #050a14   /* deeper panels */
--turf:           #1a5d3a   /* outfield green */
--turf-bright:    #2d8a52   /* lane glow */
--chalk:          #f4f1e8   /* baselines, primary text */
--chalk-dim:      #a8a59a
--dirt:           #8b6f47   /* infield */
--scoreboard-amber: #ffb627 /* LED dot matrix */
--scoreboard-green: #7dd87d
--hr-gold:        #ffd700   /* home-run / win state */
--foul-red:       #e63946   /* changes requested, danger */
--rain-blue:      #4a7ba7   /* blocked */
--ump-purple:     #6b4e8f   /* awaiting review */
```

Persona accents (kept from existing seed):
- Haiku / Leadoff Rookie — violet `#a78bfa`
- Sonnet / Bench Coach — sky `#60a5fa`
- Sonnet Triage / Advance Scout — mint `#34d399`
- Opus / Cleanup Slugger — rose `#f472b6`
- Opus Patch / Crew Chief Umpire — crimson `#fb7185`

**Typography:**
- `Press Start 2P` — scoreboard digits, lane titles, oversized CTAs, "HOME RUN" callouts. Limit usage — it's loud.
- `VT323` — secondary scoreboard text (stats lines, chip labels). More readable at small sizes than Press Start.
- `Inter Tight` — body copy, form labels, task titles, prose.
- `JetBrains Mono` — retained for `task_id`, `run_id`, file paths, logs.

Load all four via `<link>` in `base.html` (Google Fonts). Add `font-display: swap`.

**Pixel sprites (new, stored in `static/sprites/`):**

SVG files rendered at native 32×32 or 48×48 scaled up with `image-rendering: pixelated`. One sprite per persona role (`rookie.svg`, `bench_coach.svg`, `scout.svg`, `slugger.svg`, `umpire.svg`), plus:
- `ball.svg` — used in the swoosh animation
- `bat.svg` — used in running-task idle swing
- `mask.svg` — umpire mask for review states
- `rain.svg` — rain overlay for blocked state
- `trophy.svg` — HOF / shipped patch
- `crosshatch.svg` — foul territory pattern fill

Each sprite is a single-color SVG with `currentColor` so it inherits the persona's accent.

**Motion language:**
- `@keyframes pulse-pitch` — gentle scale 1.00 ↔ 1.03 at 1.2s for live-running "AT BAT" dots
- `@keyframes smack` — quick scale 0.95 → 1.08 → 1.0 + brightness bump on drop
- `@keyframes ball-trail` — a translated ball sprite across the card
- `@keyframes slide-safe` — lane transition card slide + bounce
- `@keyframes home-run` — gold glow burst + confetti on ship
- `@keyframes rain-drift` — slow vertical drift on blocked-card overlay
- All motion respects `prefers-reduced-motion: reduce` — wrap every `animation:` rule in a media query fallback that stills the motion.

## 4. Lane display rename (display-only)

Update `LANE_DISPLAY` in `control_plane/workflow.py`:

| Internal enum | Display label |
|---|---|
| `DRAFT` | `On Deck` |
| `READY_FOR_WORKER` | `At Bat` |
| `RUNNING` | `In Play` |
| `AWAITING_REVIEW` | `Close Play` |
| `CHANGES_REQUESTED` | `Foul Ball` |
| `BLOCKED` | `Rain Delay` |
| `DONE` | `Safe` |
| `LIVE` | `In The Books` |
| `ARCHIVED` | `Trophy Case` |

No changes to `WORKFLOW_LANES`, `permissions.py`, `task_events`, or any state-derivation logic.

## 5. Page-by-page redesign

### 5.1 `base.html` — scoreboard shell

Replaces `.topbar` with a single sticky scoreboard panel (~80px tall) laid out as:
- **Left:** brand "DUGOUT OS · BOT_BRIDGE", bot version chip (`●BOT v0.4.2 live`), shipped-patch count ("INN 7"), outs indicator (open critical guardrails → "OUTS 2"), lightweight live counts ("🏁 3 at bat · ⚾ 1 in play").
- **Center:** nav tabs styled as dugout signage — `[ BOARD ] [ ROSTER ] [ PATCHES ] [ ARTIFACTS ] [ SYSTEM ]`.
- **Right:** role picker (`acting: [▾]`), Claude CLI status chip (existing), two secondary action buttons (Regenerate board.md, Re-import) reduced to icon-only with tooltips.
- **The primary CTA**, centered and unmissable: **"⚾ STEP UP TO THE PLATE"** — 240px wide, chalk-white pixel font on navy, gold outline, pulses gently. Opens the task composer modal (`/tasks/new`).

Patch banner (the "Pending release" strip) becomes a **between-innings ticker** — horizontally scrolling text band right under the scoreboard when `PENDING_PATCH` is set. Keeps all existing content and buttons; just restyled.

Footer becomes a thin stadium LED-ribbon ticker with `repo / db / port`.

### 5.2 `board.html` — scoreboard dashboard

**Order top-to-bottom:**
1. Roster strip (horizontal, replaces `.agent-palette`) — one trading card per active persona.
2. Filter/search bar (the current `.filters`) restyled as a dot-matrix scouting-report strip.
3. Loop-back row (Foul Ball, `CHANGES_REQUESTED`) if populated — dashed-red ribbon above main board.
4. Main lane grid — 6 columns, color-coded per lane.

**Roster strip card (per active persona):**
- 48×48 pixel sprite (idle animation)
- Jersey number in giant scoreboard digits
- Name + role line (`Haiku · Leadoff Rookie`)
- Stat line: `AVG .287 · HR 4 · RBI 12 · G 42`
- XP bar beneath (progress to next level; one level per 10 completed runs)
- Drag source (keeps current `draggable="true"`, `data-profile-id`, `data-allowed-states`)
- On drag-start: eligible board cards glow green ("GO!"), ineligible cards darken ("NOT IN RELIEF")
- Trailing "🎟 Sign New" button on the strip when any role slot is unfilled

**Task card (the baseball trading card):**

Keeps every existing data attribute (`data-task-id`, `data-workflow-state`, `card-trash` button, `card-signals`, `card-link`, `card-dropzone`). Visual treatment:
- Rounded 8px outer, 4px inner stitching border
- Header band with stadium-green gradient containing `task_id` (mono) + `title` (pixel font)
- Priority chip as team-patch style (e.g., `● HIGH` in foul-red pixel chip)
- Track chip, subsystem chip, role chip — all restyled as LED tiles
- Assigned agent shown as "🎽 #42 Bench Coach" with the persona sprite mini-inlined
- If `workflow_state == 'RUNNING'`: "⚾ AT BAT — live 00:42" banner with pulse-pitch animation
- Age badges (`NEW` / `STALE`) as corner pennants
- Attempt badge (`×N`) unchanged in position, restyled as "AT ×N"
- Blocked card: rain overlay SVG with `rain-drift` animation, rest of card tinted rain-blue
- Drop zone retains "drop an agent here" but styled as a chalk-line batter's box

### 5.3 `task_new.html` — "Step Up to the Plate"

Accessed via the big CTA or direct `/tasks/new`. Full-screen split layout:

- **Left 50%:** the form, grouped into four pixel-bordered panels:
  1. *Scorecard* — `task_id`, `title`, `priority`, `subsystem`, `type`
  2. *Coaching* — `status`, `assigned_role` (renders as a row of mini persona cards, clickable to select)
  3. *Playbook* — `allowed_files`, `forbidden_files`
  4. *Game Plan* — `acceptance`, `notes`
- **Right 50%:** live preview of the task card as it will appear on the board, updating on every keystroke.
- **Footer:** "⚾ PLAY BALL — Create Task" primary CTA + "BACK TO DUGOUT" ghost button.

All POST payload keys remain identical to the current implementation.

### 5.4 `task_detail.html` — "At-Bat View"

- **Hero band** (replaces `task-header`): pitcher-mound backdrop image, giant pixel title, `task_id` in scoreboard mono, state chip as a **count indicator** ("Balls 2 / Strikes 1" where balls = rework attempts - 1, strikes = reviews requested; decorative, not authoritative).
- **Block banner** (if `block_reason`): "RAIN DELAY" banner with rain overlay.
- **Bullpen strip** (replaces `.agent-palette` for launch): horizontal rail of persona launch buttons; each button shows sprite + jersey # + tagline + `GO!` pill if eligible, dimmed if not. Launch adapter dropdown retained as a small bat-tag styled control to the right.
- **Controls bar**: arcade buttons with chunky 3D pixel borders. Same six buttons, same handlers.
- **Park form** (`#park-form`) restyled as a "RAIN DELAY request" panel.
- **Live-run panel** (`#live-run`) becomes the **broadcast booth**: "ON AIR" red dot, waveform accent on the log pane, cancel button as umpire "OUT" gesture.
- **Result card**: play-by-play scorebox with SAFE/OUT/REVIEW verdict.
- **Two-column body** kept; side panel sections get small scoreboard headers:
  - Allowed files → "PLAYBOOK — eligible paths"
  - Forbidden files → "PLAYBOOK — foul territory"
  - Linked artifacts → "TAPE ROOM"
  - Runs → "INNINGS LOG"
  - Reviews → "UMPIRE RULINGS"

### 5.5 `patches.html` — "Box Score"

- **Pending release** panel = giant scoreboard with pixel-flip version digits; task list = lineup card; "SHIP IT — HOME RUN!" button in gold with `home-run` hover animation.
- **Shipped history** = stack of game-program spines, clickable to `patch_detail`.
- `patch_detail.html` redesigned as a vintage MLB-program page: table of contents (task list), box-score sidebar (agents credited with RBI counts from tasks shipped), patch notes as program copy.

### 5.6 `system.html` — "Clubhouse"

- **Guardrails** = 5-turnstile row; each turnstile is a pixel gate with green ✓ / amber ⚠ / red ✗ badge; violating paths expand in a clipboard drawer.
- **Claude CLI panel** = bat rack: resolved path, version, source as labeled bats. Override input as a bat-tag. Same four buttons (Save+test, Test current, Clear override, plus implicit reload) styled as arcade buttons.
- **runtime/state.json** → retractable scoreboard drawer (keeps the `<pre class="markdown">` block behind a `<details>` for less noise at rest).
- **Launcher / Bot / Config hash** side → dugout-phone panel.

### 5.7 `artifacts.html` — "Tape Room"

Table stays a table. Styling:
- Header title "TAPE ROOM — every pitch on record"
- Alternating chalk-line row backgrounds
- Kind chips as film-canister labels (small SVG icon beside each kind)
- Search/filter bar styled as a video scrub bar
- Artifact detail page (`artifact.html`) gets a film-reel header and keeps its existing content layout.

### 5.8 `404.html` — "Rain Delay"

Full-bleed rainy scoreboard illustration. Big pixel text "RAIN DELAY — no play at that URL." Link back to Board styled as "RETURN TO DUGOUT."

### 5.9 New: `/roster` — "Front Office"

New Flask blueprint `routes/roster.py`. Lists all five role slots with:
- The active persona's full trading card (sprite, jersey, stats, tagline, signed date).
- If role is vacant: placeholder "OPEN TRYOUT" slot with a "🎟 Sign Replacement" button.
- Per active card: "RELEASE" button (red, arcade-style) that opens a confirm modal asking for a reason.

### 5.10 New: `/roster/graveyard` — "Hall of Fame / Graveyard"

Wall of retired persona cards sorted by career AVG. Each card shows:
- Final stat line (AVG, HR, RBI, G, K, BB, tenure in days).
- Retirement reason + date.
- HOF ribbon if career `AVG ≥ .300` OR career `HR ≥ 10`.
- Link to the runs they worked on via an artifact-list filter query (`/artifacts?profile_id=<id>` — a new query param added to `routes/artifacts.py`, joined through `runs.profile_id`).

## 6. Roster management — schema + endpoints

### 6.1 DB additions (`control_plane/db.py`)

Add to `agent_profiles` table via `_add_column_if_missing`:
- `status TEXT NOT NULL DEFAULT 'ACTIVE'` — one of `ACTIVE` or `RELEASED`
- `signed_at TEXT` — ISO timestamp; backfilled to the earliest run's `created_at` for existing rows on migration, or to "now" if no runs exist yet
- `released_at TEXT` — ISO timestamp, NULL for active
- `released_reason TEXT` — NULL for active
- `jersey_number INTEGER` — backfilled from the current seeded taglines (Haiku=7, Sonnet=42, Triage=11, Opus=99, Opus·Patch=1) and constrained unique across all rows (active + released) so retired numbers aren't reused

No separate stats table. Stats derive from `runs` joined on `profile_id`. Aggregations:
- `G` = count(runs)
- `AVG` = count(runs where status = 'SUCCEEDED' or exit_code = 0) / G
- `K` = count(runs where status = 'FAILED' or exit_code != 0)
- `BB` = count(runs where status in ('CANCELLED','TIMEOUT'))
- `RBI` = count(distinct tasks reached DONE via a run by this persona, joined through `task_events`)
- `HR` = count(distinct shipped patches that include a task this persona contributed to, via `task_events` + `patches`)
- `ERA` = (changes_requested reviews / total reviews) — only for review/audit roles

Keep aggregation in a new `control_plane/stats.py` module with a `persona_stats(profile_id) -> dict` function so it's cached / testable / reusable by both the roster page and the board strip.

### 6.2 New endpoints (`routes/roster.py`)

- `GET /roster` — Front Office page
- `GET /roster/graveyard` — Graveyard page
- `POST /api/roster/<profile_id>/release` — body: `{reason: str}`. Preconditions: no active runs with this profile. Sets `status='RELEASED'`, `released_at=now()`, `released_reason=reason`. Guardrail: returns 409 if an active run exists.
- `POST /api/roster/<role>/sign` — body: `{name?: str}`. Generates a new persona row for the given role with the same `adapter`/`model` and a random (or supplied) MLB-flavored name, random unused jersey number, role-palette-appropriate color, default sprite. Sets `status='ACTIVE'`, `signed_at=now()`.
- `GET /api/roster/stats/<profile_id>` — returns JSON stat line for live UI refresh.

### 6.3 Name generator

In `control_plane/roster_names.py`: two lists (first names, last names) of ~80 plausible MLB-flavored names each; `generate_name()` picks a first + last + optional nickname (`"Smoke"`, `"The Kid"`, `"Ice"`, etc.) from a nickname pool ~40 entries. Determinism via `random.Random()` seeded at call time — not reproducible; that's fine.

### 6.4 Permissions

Add to `permissions.py`:
- `release_persona` — operator only
- `sign_persona` — operator only

Deny-by-default stays the rule.

## 7. Component inventory (new CSS classes + sprites)

CSS (added to `app.css`, organized under `/* === DUGOUT OS === */` banner):
- `.scoreboard`, `.scoreboard-band`, `.scoreboard-digits`
- `.btn-pixel`, `.btn-pixel-sm`, `.btn-pixel-md`, `.btn-pixel-lg`, `.btn-pixel-primary`, `.btn-pixel-accent`, `.btn-pixel-danger`, `.btn-pixel-ghost`
- `.chip-pixel`, `.chip-pixel-led`
- `.player-card`, `.player-card-sprite`, `.player-card-jersey`, `.player-card-stats`, `.player-card-xp`
- `.task-card-trading` (replaces or extends `.card`)
- `.lane-pixel`, `.lane-pixel-header`
- `.hero-mound`, `.broadcast-booth`, `.bullpen-strip`
- `.turnstile`, `.bat-rack`, `.tape-row`
- `.between-innings-ticker`
- `.rain-overlay`, `.foul-territory-pattern`, `.home-run-burst`, `.smack`
- `.cta-step-up`, `.cta-play-ball`

Sprites under `static/sprites/`:
- `rookie.svg`, `bench_coach.svg`, `scout.svg`, `slugger.svg`, `umpire.svg`
- `ball.svg`, `bat.svg`, `mask.svg`, `rain.svg`, `trophy.svg`, `crosshatch.svg`

## 8. Accessibility + reduced-motion

- All animations wrapped in `@media (prefers-reduced-motion: no-preference)`; reduced-motion users see static states.
- Color is never the sole signal: lane state also carries a pixel icon; danger/success chips carry a glyph.
- Pixel fonts only used at ≥14px equivalent; secondary stats use `VT323` which is more legible than `Press Start 2P` at small sizes.
- All buttons retain real `<button>` elements; all drag sources remain keyboard-accessible (already a gap in the current code; we don't make it worse, but fixing it is out of scope for this spec).

## 9. Backend compatibility contract

**Nothing in the backend changes except the additions called out in §6:**
- Same route names (`tasks.board`, `tasks.task_new`, `tasks.task_detail`, `patches.patches_index`, `patches.patch_detail`, `artifacts.list_artifacts`, `artifacts.artifact_detail`, `system.system_page`).
- Same POST/PATCH/DELETE/GET API surface under `/api/*`.
- Same SSE stream for runs.
- Same `data-*` attributes consumed by the existing board.html drag-drop JS.
- Same `_card_inner.html` include contract (still expects `t` in scope).
- Workflow-state enum, permissions matrix, writer-attribution header, guardrail system, and patch lifecycle are untouched.

Net additions:
1. `LANE_DISPLAY` entries replaced with baseball labels.
2. Five new columns on `agent_profiles`.
3. Four new endpoints under `/api/roster/*` and two new page routes under `/roster*`.
4. `roster_names.py`, `stats.py` modules.
5. CSS + SVG sprites.
6. Template rewrites for: `base.html`, `board.html`, `_card_inner.html`, `task_new.html`, `task_detail.html`, `patches.html`, `patch_detail.html`, `system.html`, `artifacts.html`, `artifact.html`, `404.html`, plus new `roster.html` and `graveyard.html`.

## 10. Rollout

One-shot rewrite. No feature flag. The control plane doesn't hot-reload — kill the Flask process, run the DB migration (adds the five columns, idempotent), relaunch. All state is preserved because only cosmetic columns + display strings change.

Smoke test after relaunch:
1. Board loads, all lanes render with baseball names.
2. Drag an agent onto an At-Bat card — launch succeeds, run streams.
3. Ship a pending patch — Home Run banner fires.
4. Visit `/roster`, release a persona with reason "testing", confirm card moves to `/roster/graveyard`.
5. Sign a replacement, confirm new card appears on the board roster strip with `G 0 · AVG .000`.
6. `prefers-reduced-motion: reduce` via DevTools → animations still.
7. All five anti-drift guardrails report healthy on `/system`.

## 11. Out of scope (tracked for later)

- Sound effects (the muted "8-bit ding" on transitions) — plumbed as a CSS-only no-op stub now, real audio can be added later without template changes.
- Keyboard-navigable drag-drop.
- Mobile breakpoints.
- Persona-level historical views (filtered runs for a retired persona).
- Season rollover (resetting stats per "season") — can be layered on the existing schema later.
