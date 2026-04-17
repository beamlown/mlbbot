# REVIEW: MLB_CONFIDENCE_CALIBRATION_AUDIT_001
**Decision: APPROVED — 2026-04-17**

## Summary

Solid read-only audit of MLB model confidence calibration. Worker queried `trades_sports.db` and re-ran the analysis both with and without known outliers `{183, 184, 185, 316}`. Findings are internally consistent and corroborate `MODEL_SIGNAL_QUALITY_AUDIT_001`.

## Key findings

| Bucket | n | Win rate | PnL (with outliers) | PnL (outliers removed) |
|--------|---|----------|---------------------|------------------------|
| <0.30 | 14 | 42.9% | +$91.5 | +$91.5 |
| 0.30–0.40 | 95/91 | 34.7%/31.9% | +$830.4 | -$64.9 |
| 0.40–0.50 | 44 | 29.5% | -$66.6 | -$66.6 |
| 0.55–0.60 | 14 | 14.3% | +$54.3 | +$54.3 |
| 0.60–0.65 | 83 | 16.9% | **-$826.2** | **-$826.2** |
| ≥0.70 | 7 | 14.3% | -$120.1 | -$120.1 |

**Verdict confirmed:** Confidence is structurally unreliable. Monotonicity is broken. Higher-confidence bands are materially worse. The 0.30–0.40 bucket advantage is almost entirely an outlier artifact (collapses from +$830 to -$65 when outliers are removed). The 0.60+ gated universe is the worst-performing region in the historical sample.

## Review criteria

- [x] Read-only — no production files modified
- [x] Correct files accessed (recommendation_api.py, model_bridge.py, shadow_recommendations.jsonl, trades_sports.db)
- [x] Outlier contamination correctly isolated
- [x] Findings do not contradict established audits
- [x] Actionable recommendation provided (MLB_NEAR_RESOLUTION_SANITY_AUDIT_001)

## Implications for open tasks

- NEAR_RESOLUTION_CONFIDENCE_SUPPRESSOR_001: already implemented (see separate review) — appropriate given near-resolution markets inflate confidence artificially
- The GAME_STATE_FRESHNESS_AUDIT_001 being activated next is the right follow-on: stale game state is a plausible structural driver of confidence miscalibration
- CLEAN_RUNTIME_WINDOW_AUDIT_001 remains deferred (n=0 clean-era trades); E5/E7 remain unresolvable until bot resumes trading
