# HANDOFF: MODEL_SIGNAL_QUALITY_AUDIT_001

## What you are doing
Read-only audit of model signal quality. No code changes. You are answering one central question: **does the confidence inversion finding survive outlier removal?** And four supporting questions about signal distribution, BUY_NO asymmetry, and E8 baseline.

## Why this exists
EDGE_BASELINE_AND_EXPECTANCY_AUDIT_001 found that higher confidence → lower win rate in the historical sample. The 0.30-0.40 confidence bucket has +$830 PnL and 34.7% WR, while the 0.60-0.65 bucket (what the current gate selects) has -$826 PnL and 16.9% WR. This is alarming — it suggests the gate is selecting worse signals.

BUT: the 0.30-0.40 bucket contains:
- Trades 183, 184, 185: three IDENTICAL lad-tor entries at conf=0.315, pnl=+$236 each (+$708 combined). Known duplicate-open bug.
- Trade 316: entry at 0.011 (below gate), conf=0.39, pnl=+$187. Ungated anomaly.

Together these four trades in the 0.30-0.40 bucket contribute +$895. The bucket's total PnL is +$830. **If you remove these four outliers, the 0.30-0.40 bucket probably goes negative.** If that's true, confidence inversion disappears and the gate setting is fine — it's just operating on insufficient post-restart data.

Your job is to verify this arithmetic and answer the supporting signal questions.

## Data sources

### 1. trades_sports.db
Path: `C:\Users\johnny\Desktop\sports_bot_v2\trades_sports.db`
Table: `trades`, filter to `status='closed'` and `pnl_usd IS NOT NULL` and `pnl_usd != 0`.

Columns used: `id, ts_open, confidence, entry_px, pnl_usd, fees_usd, side, reason_close, market_slug, status`

**pnl_usd is already net of fees.** Do not subtract fees_usd again.

Outlier trades to exclude in cleaned analyses (S1, S2):
- ids: 183, 184, 185 (lad-tor duplicate cluster, conf=0.315)
- ids: 310, 316 (ungated near-resolution entries, entry < 0.22)

### 2. shadow_recommendations.jsonl
Path: `C:\Users\johnny\Desktop\mlb_model\logs\shadow_recommendations.jsonl`
Format: JSONL — one JSON object per line. Some lines may be empty or invalid — skip them with try/except.

Key fields:
- `action`: "BUY_YES", "BUY_NO", "NO_TRADE"
- `confidence`: float — the model confidence score (same formula as trades DB)
- `market_slug`: string — may match trades DB market_slug
- `edge_yes`, `edge_no`: raw edge values before confidence scaling
- `data_quality`: float — model data quality score
- `spread_quality` is NOT stored separately — it's baked into confidence
- `ts`: ISO8601 timestamp
- `inning`, `score_diff`, `game_progress`, `game_status`: game state at recommendation time

Volume: ~63,000 total lines. ~18,760 BUY_YES/BUY_NO recs. ~44,285 NO_TRADE recs. No outcome events (0 lines with event_type='outcome').

### 3. recommendation_api.py (read-only reference)
Path: `C:\Users\johnny\Desktop\mlb_model\integration\recommendation_api.py`
Read this to understand the confidence formula if needed. Key lines:
```python
edge_score = min(1.0, max(0.0, (edge_candidate - min_edge) / 0.10 + 0.5))
confidence = round(edge_score * infer_result.data_quality * spread_quality, 4)
```
With `MIN_EDGE_THRESHOLD=0.05` (default). Edge_score saturates at 1.0 when edge >= 0.15.

## Critical question for S8 (shadow-to-DB matching)

The shadow log does NOT have outcome events. To match shadow recs to trade outcomes, you must join by market_slug across the two data sources:
- Shadow rec: `market_slug` field (e.g., "mlb-lad-tor-2026-04-08")
- DB trade: `market_slug` column (same format)

Match on exact `market_slug`. For each matched market, the trade outcome tells you whether the recommendation was correct. Note: many shadow recs will not have a corresponding DB trade (the gate blocked them). Focus on matching recs where the DB also has a trade entry for that slug, and compare confidence-at-recommendation to trade outcome.

## What NOT to do
- Do not edit any file
- Do not open new tasks — return findings only
- Do not compute on `status='open'` trades
- Do not subtract fees_usd from pnl_usd (already net)
- Do not treat S8 failure (no matches) as a blocker — just report the gap

## Confidence inversion hypothesis to test

**Hypothesis A (inversion disappears):** After removing trades 183, 184, 185, 310, 316 from the 0.30-0.40 bucket, that bucket goes negative. The 0.60-0.65 bucket becomes relatively better (still negative but not dramatically worse than 0.30-0.40). Confidence is not genuinely anti-predictive — the inversion was sample-size noise plus outlier contamination. The current gate is defensible.

**Hypothesis B (inversion persists):** After removing outliers, 0.30-0.40 bucket still outperforms 0.60-0.65 by a material margin. Confidence IS genuinely anti-predictive in the current model. The gate is selecting worse signals. A deeper model investigation is needed.

State which hypothesis the data supports, with the cleaned numbers.

## Your result must contain
For each of S1-S9:
- The query/method used
- The result numbers
- One-sentence interpretation

Final section:
- `confidence_inversion_verdict`: does inversion survive outlier removal? YES / NO / PARTIALLY
- `buy_no_advantage_verdict`: is BUY_NO advantage structural or outlier-driven? STRUCTURAL / OUTLIER_DRIVEN / AMBIGUOUS
- `e8_verdict`: E8 PASS / FAIL / INSUFFICIENT_DATA
- `primary_finding`: 2-3 sentence summary of what the signal quality picture looks like
