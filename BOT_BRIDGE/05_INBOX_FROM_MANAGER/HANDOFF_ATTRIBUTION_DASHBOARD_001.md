<!-- writer: manager, task_id: ATTRIBUTION_DASHBOARD_001, patch_id: pending, written_at: 2026-04-18T17:35:49Z, attempt: 1 -->

# HANDOFF: ATTRIBUTION_DASHBOARD_001

## Status
QUEUED — P0 phase, Attribution Spine. Depends on TRADE_ATTRIBUTION_WIRING_001.

## What you are doing
Add attribution-focused panels to the dashboard so the operator can answer
"is the model calibrated?" and "where does our edge come from?" in ≤ 10 seconds.
All data reads MUST come from `trades_sports.db` — no in-memory or derived state.

## Why this exists
Schema + wiring populate data. This task makes it visible in a way that drives
the operator's next decision: keep, tune, or kill a config.

## Target files
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py` — new endpoints
- `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html` — new section (prefer dashboard.html; if `dashboard_v2.html` is now authoritative, use that and note which)
- Any JS helpers kept inline in the HTML

## Panels to add (section: "Attribution")

### Panel A — Calibration curve
X axis: predicted win prob bucketed (0.5–0.55, 0.55–0.6, …, 0.9+)
Y axis: realized win rate in that bucket (count of wins / count of resolved trades)
Overlay: 45° diagonal (perfect calibration reference)
Tooltip per bucket: `n`, `predicted`, `realized`, `Brier contribution`
Data source: `SELECT entry_model_prob, model_side_was_right FROM trades WHERE model_side_was_right IS NOT NULL`

### Panel B — Edge realization scatter
X axis: expected_edge_pct at entry
Y axis: realized_pnl
Point color: trade_class (5 colors)
Diagonal line: y = x * size_avg (rough "perfect realization" reference)
Purpose: visually spot whether higher expected-edge trades actually deliver higher P&L

### Panel C — Hit rate by confidence bucket
Table: confidence bucket (entry_model_prob rounded to 0.05), n, hit rate (%), mean realized P&L, Brier
Sorted by bucket ascending
Purpose: see if high-confidence picks actually win more

### Panel D — Trade class breakdown
Donut / stacked bar: count of each trade_class
Below: net P&L per class (MODEL_LOSS_EXECUTION P&L is the "money lost to slippage/stops despite being right" — this is a key number)

## Dashboard endpoint contract

New endpoint `GET /api/attribution/summary?since=<iso_date>`:
```json
{
  "since": "2026-04-01",
  "n_resolved": 147,
  "calibration": [
    {"bucket_lo": 0.50, "bucket_hi": 0.55, "n": 12, "predicted_mean": 0.527, "realized_rate": 0.500},
    ...
  ],
  "trade_classes": {
    "MODEL_WIN_EXPECTED": {"n": 61, "pnl": 412.30},
    "MODEL_WIN_LUCKY": {"n": 8, "pnl": 55.10},
    "MODEL_LOSS_EXPECTED": {"n": 14, "pnl": -92.40},
    "MODEL_LOSS_EXECUTION": {"n": 22, "pnl": -180.00},
    "UNRESOLVED": {"n": 42, "pnl": 0.00}
  },
  "brier_score": 0.187,
  "log_loss": 0.542
}
```

And `GET /api/attribution/edge_scatter?since=<iso_date>` returning point array.

## Data authority
- All reads from `trades_sports.db` only
- No fallback to in-memory caches, no fallback to paper_trades.db
- If a field is NULL, surface it as "n/a" rather than guessing

## Truthfulness guardrails (apply prior DASHBOARD_TRUTH lessons)
- Every panel must include `n` (sample size). No panels hide low-sample-size.
- Every panel must include the `since` cutoff it was computed over.
- If `n < 20` in any bucket, render muted + tooltip: "low sample — not statistically meaningful yet."
- Auto-refresh interval: match existing dashboard convention (check dashboard.html / dashboard_v2.html).

## Output / deliverables
1. Modified dashboard_server.py with two new endpoints
2. Modified dashboard HTML with Attribution section containing 4 panels
3. Result JSON at `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_ATTRIBUTION_DASHBOARD_001.json`

## Result JSON fields required
```json
{
  "task_id": "ATTRIBUTION_DASHBOARD_001",
  "status": "ok",
  "endpoints_added": ["/api/attribution/summary", "/api/attribution/edge_scatter"],
  "panels_added": ["calibration_curve", "edge_scatter", "hit_rate_table", "trade_class_breakdown"],
  "dashboard_file_authoritative": "dashboard.html OR dashboard_v2.html",
  "data_source_verification": "SELECT statements listed",
  "files_changed": ["..."]
}
```

## Do NOT do
- Do not modify the DB schema
- Do not modify attribution wiring
- Do not touch any existing dashboard panel
- Do not change /api/ endpoints other than adding the two new ones
- Do not introduce new JS libraries beyond what dashboard already uses
- No changes to bot_core, paper_exec, risk, or model code
- No real-money paths
