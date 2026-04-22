# REVIEW — ATTRIBUTION_DASHBOARD_001

Patch: PATCH_1 (version 0.4.2), step 1 of 10
Reviewer: PATCH REVIEWER
Reviewed files:
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_v2.html`

## Summary of work
Worker added two endpoints (`/api/attribution/summary`,
`/api/attribution/edge_scatter`) and an "Attribution" section to
`dashboard_v2.html` with four panels (calibration canvas, edge scatter
canvas, hit-rate table, trade-class breakdown). SQL reads from
`trades_sports.db` via `_db()` — no paper_trades fallback, no schema
changes, no existing-panel edits. Matches the data-source guardrail.

## Positives
- Server helpers `_get_attribution_summary` and `_get_edge_scatter`
  (dashboard_server.py:913, dashboard_server.py:1014) read only from
  `trades` table with NULL guards; parameterized `since` passed as
  bound value. SELECT statements match the RESULT JSON.
- Route dispatch at dashboard_server.py:1101 and :1107 is additive
  and leaves other endpoints untouched.
- HTML section block is scoped under a new `<div class="section">` at
  dashboard_v2.html:174 — no prior markup modified.
- `n_resolved`, per-bucket `n`, Brier, log-loss computed as spec'd;
  donut replaced with stacked bars (acceptable per "donut / stacked
  bar" wording).

## BLOCKING ISSUE — dashboard_v2.html has a SyntaxError

Lines 350 and 367 contain a malformed ternary that I believe will
prevent the entire `<script>` block from parsing:

```
const tooltip=lowSample?` title="Low sample size (n=${n}) — not statistically meaningful yet":'`;
```

Tokenization:
- `?` opens the ternary
- the first `` ` `` opens a template literal
- the `":'` sequence is inside that literal, not ternary syntax
- the second `` ` `` closes the literal
- `;` ends the statement

That leaves `lowSample ? <templateLiteral>;` — no `:` branch. This
is a JS SyntaxError at parse time. In a single inline `<script>`,
one parse error voids every function defined in the block. That
includes `poll()`, `renderTop()`, `renderMonitor()`, all existing
dashboard renderers. In practical terms this does not just break
the new Attribution section — it likely breaks the whole v2
dashboard on load.

Same pattern repeats at dashboard_v2.html:367 inside
`renderTradeClasses`.

Intended form was almost certainly:
```js
const tooltip = lowSample ? ` title="Low sample size (n=${n}) — not statistically meaningful yet"` : '';
```

The closing backtick got swapped with the `:` and the empty-string
else branch was lost.

I did not run the dashboard to confirm parse failure (read-only
review), but the tokenization is unambiguous. Worker did not report
a browser verification step; the bug would be caught on first load
of `/v2`.

## Secondary issues (worth fixing, not blocking on their own)
- `log.error('Attribution fetch error:',e)` at dashboard_v2.html:378
  — `log` is undefined in browser scope (it's a Python logger
  name elsewhere). Should be `console.error`. Currently masked by a
  broader `try/catch`, but logs nothing useful.
- Canvas text uses `ctx.fillStyle='var(--text)'`
  (dashboard_v2.html:293, :294, :295, :338, :339). Canvas does not
  resolve CSS custom properties; axis labels will fall back to an
  invalid colour and likely render as default black or not at all.
- Handoff requires panels to surface the `since` cutoff and the
  `n` context. `n` is shown per-bucket, but the `since` value
  returned by the API is never rendered in the UI. Client hardcodes
  `since='2000-01-01'` (dashboard_v2.html:373), so the API's
  `since` parameter is effectively cosmetic.
- Spec asked Panel B for a `y = x * size_avg` reference line.
  Scatter has axes + grid but no reference line.

## Scope / guardrails
- No schema change. ✓
- No attribution-wiring change. ✓
- No other `/api/` endpoints touched. ✓
- No real-money / bot_core / paper_exec / risk / model edits. ✓
- Files modified match `files_changed` in RESULT. ✓

## Drift from prior steps
First step of PATCH_1 — no prior-step TL;DRs to compare against.
RESULT claims `role: HAIKU_WORKER`; per memory, SONNET_WORKER is
preferred for complex tasks. Worth flagging to the synthesis step
but not a review blocker on its own.

DECISION: CHANGES_REQUESTED — broken ternary at dashboard_v2.html:350 and :367 introduces a JS SyntaxError that likely voids the entire `<script>` block

TL;DR:
- Server endpoints and SQL reads look clean and match handoff contract
- BLOCKING: dashboard_v2.html:350 and :367 have a malformed ternary (`lowSample?\` … \":'\``) that is a parse-time SyntaxError
- One parse error in this inline script block would kill every existing dashboard renderer, not just the new section
- Secondary nits: `log.error` undefined in browser, canvas `fillStyle='var(--text)'` won't resolve, `since` cutoff not shown in UI, scatter missing `y=x*size_avg` reference line
- No schema / wiring / existing-panel drift; scope guardrails respected, but cannot ship until the JS parse bug is fixed and verified in a browser
