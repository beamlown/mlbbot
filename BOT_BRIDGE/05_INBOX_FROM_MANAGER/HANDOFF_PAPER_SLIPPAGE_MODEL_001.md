<!-- writer: manager, task_id: PAPER_SLIPPAGE_MODEL_001, patch_id: pending, written_at: 2026-04-18T17:35:49Z, attempt: 1 -->

# HANDOFF: PAPER_SLIPPAGE_MODEL_001

## Status
QUEUED — P1 phase, execution realism. Independent of P0 but attribution will
observe its effects (`expected_edge_pct` vs `realized_pnl` gap).

## What you are doing
Add a realistic slippage / fill-price model to paper execution so paper fills
reflect what real-money orders would actually get on Polymarket, rather than
idealized mid or best.

## Why this exists
Paper mode currently (verify this — may already be walking the book) fills at
best bid/ask or mid. Real-money orders eat book depth, especially at the sizes
the bot trades. If paper is filling at better prices than reality, then:
- Edge measurements are optimistic
- Any strategy that *looks* profitable in paper may be flat or negative in live
- We cannot trust the attribution data from P0 downstream

The slippage model must be conservative (assume real orders are not first in
queue) and parameterized (so we can tune once attribution exposes the
real-vs-expected gap).

## Target files
- `C:\Users\johnny\Desktop\sports_bot_v2\core\paper_exec.py` — fill logic
- `C:\Users\johnny\Desktop\sports_bot_v2\core\orderbook.py` — may already have
  helpers to walk the book; reuse if so
- Possibly `C:\Users\johnny\Desktop\sports_bot_v2\core\types.py` — new fields
  on fill record if not already present
- New config entry somewhere in runtime config (follow existing convention —
  check bot_core.py / .env for pattern)

## Required behavior

### 1. Walk-the-book fill
Given an order side + desired size + current orderbook snapshot:
- Compute volume-weighted average fill price by consuming liquidity from the
  opposite side, starting at the best quote
- If orderbook depth is insufficient for desired size, partial fill + record
  `partial_fill = True`

### 2. Slippage buffer (parameterizable)
On top of walk-the-book price, apply a configurable slippage buffer (bps or
cents). Default to a conservative value — suggest 2 cents above walk-the-book
fill price for buys, or 2% of mid as a starting heuristic. Actual default
should match what the Polymarket orderbook typically shows (check an
`ob_snapshots/` sample before committing a default).

### 3. Toggle
Must be toggleable via config: `paper_slippage_enabled` (bool) +
`paper_slippage_cents` (float). Default enabled.

### 4. Attribution integration (light touch)
The paper fill result must populate `actual_fill_px` in the attribution record.
This is already the contract from TRADE_ATTRIBUTION_WIRING_001; if that task
hasn't landed yet, still populate whatever the current paper-exec return
record exposes.

### 5. Logging
Per-fill log line: `order_id | side | desired_size | filled_size | wbap | fill_px | slippage_bps | partial`

## Verification inputs
Use an `ob_snapshots/*.json` sample as a known input and show your slippage
model's output for 3 sizes: small (1% of top-of-book depth), medium (50% of
top-of-book depth), large (exceeds top-of-book). Include the fill comparison
table in the result JSON.

## Output / deliverables
1. Modified paper_exec.py + any helpers
2. New config entries (documented in result JSON)
3. Example fill comparison table
4. Result JSON at `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_PAPER_SLIPPAGE_MODEL_001.json`

## Result JSON fields required
```json
{
  "task_id": "PAPER_SLIPPAGE_MODEL_001",
  "status": "ok",
  "config_entries_added": ["paper_slippage_enabled", "paper_slippage_cents"],
  "default_slippage_cents": 2.0,
  "example_fills": [
    {"size": "...", "wbap_without_slippage": 0.54, "fill_px_with_slippage": 0.5420, "partial": false}
  ],
  "files_changed": ["..."]
}
```

## Do NOT do
- Do not change entry/exit decision logic
- Do not change bankroll or sizing
- Do not change live real-money execution (there is none, but keep the
  boundary — no new live execution code)
- Do not modify orderbook data model beyond adding fill-output fields
- Do not introduce a slippage curve that depends on side identity (buyer vs
  seller) beyond the symmetric default
- Do not touch attribution schema
